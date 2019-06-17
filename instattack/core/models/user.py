import asyncio
import os
from plumbum.path import LocalPath

from tortoise import fields
from tortoise.models import Model
from tortoise.exceptions import OperationalError, DoesNotExist

from instattack.config import constants
from instattack.lib import logger
from instattack.lib.utils import stream_raw_data, read_raw_data

from instattack.core.exceptions import DirExists, UserFileExists
from instattack.core.passwords import password_gen


log = logger.get(__name__, subname='User')


class UserAttempt(Model):

    id = fields.IntField(pk=True)
    password = fields.CharField(max_length=100)
    user = fields.ForeignKeyField('models.User', related_name='attempts')
    last_attempt = fields.DatetimeField(null=True, auto_now=True)
    success = fields.BooleanField(default=False)
    num_attempts = fields.IntField(default=1)

    class Meta:
        unique_together = ('password', 'user')


class User(Model):
    """
    TODO
    ----
    Since we do not setup the user directories on retrieval from DB, only on
    save, there is a potential we will hit a bug if we try to read from the
    files and they were deleted.
    """
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=30)

    # Successful password attepmt, a little repetitive since we will also
    # have it in the attempts, but just in case for now.
    password = fields.CharField(max_length=100, null=True)
    date_created = fields.DatetimeField(auto_now_add=True)
    birthday = fields.DatetimeField(null=True)

    FILES = constants.USER_FILES

    class Meta:
        unique_together = ('username', )

    async def delete(self, *args, **kwargs):
        self.teardown()
        await super(User, self).delete(*args, **kwargs)

    async def save(self, *args, **kwargs):
        self.setup()
        await super(User, self).save(*args, **kwargs)

    def initialize_directory(self):
        """
        Creates the User directory from scratch with required files.
        """
        if self.directory.exists():
            raise DirExists(self.directory)

        self.directory.mkdir()
        for filename in self.FILES:
            filepath = self.file_path(filename)
            if filepath.exists():
                raise UserFileExists(filepath, self)
            filepath.touch()

    def setup(self):
        """
        TODO:
        ----
        We do this when a user is saved to the database, but we should see if
        we can do it everytime the user is also retrieved from the database.
        """
        if not self.directory.exists():
            self.initialize_directory()
        else:
            missing_files = self.find_missing_files()
            if len(missing_files) != 0:
                for filepath in missing_files:
                    log.warning(f'File {filepath.name} was accidentally deleted.')
                    filepath.touch()

    def teardown(self):
        if not self.directory.exists():
            log.warning(f'User directory {self.directory.name} was already deleted.')
        else:
            self.directory.delete()

    @property
    def directory(self):
        path = os.path.join(constants.USER_DIR, self.username)
        return LocalPath(path)

    def file_path(self, filename):
        if '.txt' not in filename:
            filename = f"{filename}.txt"
        return self.directory / filename

    def find_missing_files(self):
        """
        Called when creating a new user.
        """
        missing = []
        for filename in self.FILES:
            filepath = self.file_path(filename)
            if not filepath.exists() or not filepath.is_file():
                missing.append(filepath)
        return missing

    async def stream_data(self, filename, limit=None):
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        if not self.directory.exists():
            log.warning(f'User Directory for {self.username} Does Not Exist')
            self.directory.mkdir()

        filepath = self.file_path(filename)
        if not filepath:
            log.warning(f"File {filepath.name} Does Not Exist.")
            filepath.touch()

        async for item in stream_raw_data(filepath, limit=limit):
            yield item

    def read_data(self, filename, limit=None):
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        if not self.directory.exists():
            log.warning(f'User Directory for {self.username} Does Not Exist')
            self.directory.mkdir()

        filepath = self.file_path(filename)
        if not filepath:
            log.warning(f"File {filepath.name} Does Not Exist.")
            filepath.touch()

        return read_raw_data(filepath, limit=limit)

    def get_passwords(self, limit=None):
        return self.read_data(constants.PASSWORDS, limit=limit)

    def get_alterations(self, limit=None):
        return self.read_data(constants.ALTERATIONS, limit=limit)

    def get_numerics(self, limit=None):
        return self.read_data(constants.NUMERICS, limit=limit)

    async def stream_passwords(self, limit=None):
        async for item in self.stream_data(constants.PASSWORDS, limit=limit):
            yield item

    async def stream_alterations(self, limit=None):
        async for item in self.stream_data(constants.ALTERATIONS, limit=limit):
            yield item

    async def stream_numerics(self, limit=None):
        async for item in self.stream_data(constants.NUMERICS, limit=limit):
            yield item

    async def was_authenticated(self):
        try:
            await UserAttempt.get(user=self, success=True)
        except DoesNotExist:
            return False
        else:
            return True

    async def was_authenticated_with_password(self, password):
        try:
            attempt = await UserAttempt.get(user=self, success=True)
        except DoesNotExist:
            return False
        else:
            if attempt.password == password:
                return True
            return False

    async def clear_attempts(self, attempts=None):
        attempts = attempts or await self.get_attempts()

        tasks = []
        for attempt in attempts:
            tasks.append(attempt.delete())
        await asyncio.gather(*tasks)

    async def get_attempts(self, limit=None):
        attempts = await UserAttempt.filter(user=self).all()
        if limit:
            attempts = attempts[:limit]
        return attempts

    async def stream_attempts(self, limit=None):
        count = 0
        async for attempt in UserAttempt.filter(user=self).all():
            if limit and count == limit:
                break
            yield attempt
            count += 1

    async def create_or_update_attempt(self, attempt, success=False, try_attempt=0):
        try:
            attempt, created = await UserAttempt.get_or_create(
                defaults={
                    'success': success,
                },
                password=attempt,
                user=self,
            )
            if not created:
                attempt.success = success
                attempt.num_attempts += 1
                await attempt.save()

        except OperationalError:
            if try_attempt <= constants.USER_MAX_SAVE_ATTEMPT_TRIES:
                log.warning('Unable to Access Database...', extra={
                    'other': f'Sleeping for {constants.USER_SLEEP_ON_SAVE_FAIL} Seconds.'
                })
                await asyncio.sleep(constants.USER_SLEEP_ON_SAVE_FAIL)
                await self.create_or_update_attempt(
                    attempt,
                    success=success,
                    try_attempt=try_attempt + 1
                )

            # For now, we do not want to raise exceptions and disrupt the long
            # running logic unless there is a chance we accidentally miss a
            # confirmed password.
            else:
                if success:
                    raise
                log.critical(f'Unable to Successfully Save Attempt {attempt}.')

    async def get_new_attempts(self, loop, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        current_attempts = await self.get_attempts()
        current_attempts = [attempt.password for attempt in current_attempts]

        generated = []
        generator = password_gen(self, current_attempts, limit=limit)
        for item in generator():
            generated.append(item)

        return generated

    async def stream_new_attempts(self, loop, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        current_attempts = await self.get_attempts()
        current_attempts = [attempt.password for attempt in current_attempts]

        generator = password_gen(self, current_attempts, limit=limit)
        for item in generator():
            yield item
