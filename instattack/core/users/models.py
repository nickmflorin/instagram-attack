from __future__ import absolute_import

import asyncio
from datetime import datetime

from tortoise.exceptions import DoesNotExist
from tortoise import fields
from tortoise.models import Model

from instattack import settings
from instattack.logger import AppLogger
from instattack.lib import stream_raw_data

from .exceptions import UserDirDoesNotExist, UserFileDoesNotExist
from .generator import password_gen


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
    log = AppLogger('User')

    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=30)

    # Successful password attepmt, a little repetitive since we will also
    # have it in the attempts, but just in case for now.
    password = fields.CharField(max_length=100, null=True)

    FILES = [
        settings.PASSWORDS,
        settings.ALTERATIONS,
        settings.NUMERICS,
    ]

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
                self.log.warning(e)
                self.create_file(filename)

    def streamed_data(self, filename, limit=None):
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        try:
            filepath = self.file_path(filename, strict=True)
        except UserFileDoesNotExist as e:
            self.log.warning(e)
            filepath = self.create_file(filename)

        return stream_raw_data(filepath, limit=limit)

    async def get_passwords(self, limit=None):
        async for line in self.streamed_data(settings.PASSWORDS, limit=limit):
            yield line

    async def get_alterations(self, limit=None):
        async for line in self.streamed_data(settings.ALTERATIONS, limit=limit):
            yield line

    async def get_numerics(self, limit=None):
        async for line in self.streamed_data(settings.NUMERICS, limit=limit):
            yield line

    async def get_attempts(self, limit=None):
        attempts = await self.fetch_related('attempts')
        if not attempts:
            return []
        if limit:
            return attempts[:limit]
        return attempts

    async def write_attempts(self, queue):

        async def write_attempt(password):
            try:
                attempt = await UserAttempt.get(
                    password=password,
                    user=self,
                )
            except DoesNotExist:
                await UserAttempt.create(
                    password=password,
                    user=self,
                    last_attempt=datetime.now(),
                    success=False,  # HAVE TO FIX THIS NO WAY OF KNOWING SUCCESS
                )
            else:
                attempt.last_attempt = datetime.now()
                attempt.success = False   # HAVE TO FIX THIS NO WAY OF KNOWING SUCCESS
                await attempt.save()

        tasks = []
        while not queue.empty():
            password = queue.get_nowait()
            tasks.append(asyncio.create_task(write_attempt(password)))

        return asyncio.gather(*tasks)

    async def generate_attempts(self, loop, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        count = 0
        generator = password_gen(loop, self)

        async for password in generator():
            if count < limit:
                yield password
                count += 1
