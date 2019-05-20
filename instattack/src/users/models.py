from datetime import datetime

from tortoise import fields
from tortoise.models import Model
from tortoise.exceptions import IntegrityError

from instattack import logger
from instattack.conf import settings
from instattack.lib import stream_raw_data, read_raw_data
from instattack.src.users import constants

from .exceptions import UserDirDoesNotExist, UserFileDoesNotExist
from .generator import password_gen


log = logger.get_async('User')
log_sync = logger.get_sync('User')


class UserAttempt(Model):

    id = fields.IntField(pk=True)
    password = fields.CharField(max_length=100)
    user = fields.ForeignKeyField('models.User', related_name='attempts')
    last_attempt = fields.DatetimeField(null=True, auto_now=True)
    success = fields.BooleanField(default=False)

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

    FILES = constants.FILES

    class Meta:
        unique_together = ('id', 'username', )

    async def save(self, *args, **kwargs):
        self.setup()
        await super(User, self).save(*args, **kwargs)

    def setup(self):
        """
        TODO:
        ----
        We do this when a user is saved to the database, but we should see if
        we can do it everytime the user is also retrieved from the database.
        """
        directory = self.directory()
        if not directory.exists():
            directory.mkdir()
            self.create_files()
        else:
            self.verify_files()

    def teardown(self):
        """
        TODO
        ----
        Do this on an overridden .delete() method.
        """
        directory = self.directory()
        if directory.exists():
            directory.delete()

    def directory(self):
        return settings.USER_DIR / self.username

    def create_directory(self):
        directory = self.directory()
        if not directory.exists():
            directory.mkdir()
        return directory

    def file_path(self, filename, strict=False):
        directory = self.directory()
        if not directory.exists():
            raise UserDirDoesNotExist(directory)

        if '.txt' not in filename:
            filename = f"{filename}.txt"

        path = directory / filename
        if strict and (not path.exists() or not path.is_file()):
            raise UserFileDoesNotExist(path, self)
        return path

    def create_file(self, filename):
        filepath = self.file_path(filename)
        if not filepath.exists() or not filepath.is_file():
            filepath.touch()
        return filepath

    def create_files(self):
        """
        Called when creating a new user.
        """
        for filename in self.FILES:
            self.create_file(filename)

    def verify_files(self):
        for filename in self.FILES:
            filepath = self.file_path(filename)
            if not filepath.exists() or not filepath.is_file():
                # TODO: In rare care where the path is a directory, we may want
                # to delete it.
                e = UserFileDoesNotExist(filepath, self)
                log_sync.warning(e)
                self.create_file(filename)

    def streamed_data(self, filename, limit=None):
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        try:
            filepath = self.file_path(filename, strict=True)
        except UserFileDoesNotExist as e:
            log.warning(e)
            filepath = self.create_file(filename)

        return stream_raw_data(filepath, limit=limit)

    def read_data(self, filename, limit=None):
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        try:
            filepath = self.file_path(filename, strict=True)
        except UserFileDoesNotExist as e:
            log.warning(e)
            filepath = self.create_file(filename)

        return read_raw_data(filepath, limit=limit)

    def get_passwords(self, limit=None):
        return self.read_data(constants.PASSWORDS, limit=limit)

    def get_alterations(self, limit=None):
        return self.read_data(constants.ALTERATIONS, limit=limit)

    def get_numerics(self, limit=None):
        return self.read_data(constants.NUMERICS, limit=limit)

    async def get_attempts(self, limit=None):
        attempts = await UserAttempt.filter(user=self).all()
        if limit:
            attempts = attempts[:limit]
        return attempts

    async def write_attempt(self, attempt, success=False):
        if success:
            log.debug(f'Saving Successful Attempt {attempt} for {self.username}.')
        else:
            log.debug(f'Saving Unsuccessful Attempt {attempt} for {self.username}.')

        # Since we are calling this from a scheduler, it does not seem to pick up
        # on the exceptions that we would raise if the attempt already exists,
        # which is okay for now - since it will not create a duplicate one.
        try:
            attempt = await UserAttempt.create(
                password=attempt,
                user=self,
                success=success,
                last_attempt=datetime.now(),
            )
        except IntegrityError:
            log.warning(f'Cannot Save Duplicate Attempt {attempt}.')

    async def generate_attempts(self, loop, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        current_attempts = await self.get_attempts()
        generator = password_gen(loop, self, current_attempts, limit=limit)
        for item in generator():
            yield item
