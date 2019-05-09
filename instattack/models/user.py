from __future__ import absolute_import

from tortoise.models import Model
from tortoise import fields

from lib import AppLogger, stream_raw_data

from instattack import settings
from instattack.exceptions import (
    UserDirMissing, UserDirExists, UserFileMissing, UserFileExists,
    DirMissing)

from .passwords import password_gen
from .utils import get_users_data_dir, create_users_data_dir


log = AppLogger(__file__)


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

    PASSWORDS = "passwords"
    ALTERATIONS = "alterations"
    NUMBERS = "common_numbers"
    FILES = [
        PASSWORDS,
        ALTERATIONS,
        NUMBERS,
    ]

    class Meta:
        unique_together = ('id', 'username', )

    async def get_attempts(self):
        attempts = await self.fetch_related('attempts')
        if not attempts:
            return []
        return attempts

    async def generate_attempts(self, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        generator = password_gen(
            numerics=self.get_numbers(),
            alterations=self.get_alterations(),
            raw=self.get_passwords(),
        )
        attempts = await self.get_attempts()

        async for password in generator(attempts, limit=limit):
            self.num_passwords += 1
            yield password

    async def save(self, *args, **kwargs):
        self.setup()
        await super(User, self).save(*args, **kwargs)

    def setup(self):
        # TODO: See if we can do this everytime the user is saved or fetched
        # from the database.
        if not self.directory_setup:
            create_users_data_dir(strict=False)
            self.initialize_directory()
            self.initialize_files()
        else:
            self.verify_files()

    @property
    def directory_setup(self):
        try:
            get_users_data_dir(expected=True)
        except DirMissing as e:
            return False
        try:
            self.get_directory(expected=True, strict=True)
        except UserDirMissing:
            return False
        return True

    def get_directory(self, expected=True, strict=True, filename=None):
        path = get_users_data_dir(expected=True) / self.username

        if strict:
            if expected and not path.exists():
                raise UserDirMissing(self)

            elif not expected and path.exists():
                raise UserDirExists(self)

        if filename:
            if '.txt' not in filename:
                filename = f"{filename}.txt"
            return path / filename
        return path

    def get_file_path(self, filename, expected=True, strict=True):

        path = self.get_directory(filename=filename)
        if strict:
            if expected and not path.exists():
                raise UserFileMissing(self, filename)

            elif not expected and path.exists():
                raise UserFileExists(self, filename)

        return path

    def initialize_directory(self):
        # Will raise an exception if the directory is already there.
        user_path = self.get_directory(expected=False, strict=True)
        user_path.mkdir()
        return user_path

    def initialize_file(self, filename):
        # Will raise an exception if the file is already there.
        filepath = self.get_file_path(filename, expected=False, strict=True)
        filepath.touch()
        return filepath

    def initialize_files(self):
        """
        Called when creating a new user.
        """
        for filename in self.FILES:
            self.initialize_file(filename)

    def verify_files(self):
        for filename in self.FILES:
            try:
                self.get_file_path(filename, expected=True, strict=True)
            except UserFileMissing as e:
                log.warning(str(e))
                self.initialize_file(filename)

    async def read_file(self, filename):
        """
        TODO:
        -----
        If the file is for whatever reason non-existent, we should probably
        still create it and not issue an exception.
        """
        if filename not in self.FILES:
            raise ValueError(f'Invalid filename {filename}.')

        filepath = self.get_file_path(filename)
        if not filepath.is_file():
            raise FileNotFoundError('No such file: %s' % filepath)

        yield stream_raw_data(filepath)

    async def get_passwords(self):
        """
        TODO
        ----
        Since we do not setup the user directories on retrieval from DB, only on
        save, there is a potential we will hit a bug if we try to read from the
        files and they were deleted.
        """
        yield self.read_file(self.PASSWORDS)

    async def get_alterations(self):
        """
        TODO
        ----
        Since we do not setup the user directories on retrieval from DB, only on
        save, there is a potential we will hit a bug if we try to read from the
        files and they were deleted.
        """
        yield self.read_file(self.ALTERATIONS)

    async def get_numbers(self):
        """
        TODO
        ----
        Since we do not setup the user directories on retrieval from DB, only on
        save, there is a potential we will hit a bug if we try to read from the
        files and they were deleted.
        """
        yield self.read_file(self.NUMBERS)
