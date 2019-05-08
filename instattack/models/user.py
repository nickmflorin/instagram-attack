from __future__ import absolute_import

import os
from plumbum import local

from dataclasses import dataclass
from datetime import datetime

from lib import (create_new_user_files, check_user_files,
    create_user_dir, create_users_data_dir, user_exists, read_user_file,
    update_attempts_file, password_generator)

from instattack import settings


@dataclass
class User:

    username: str
    num_passwords: int = 0
    password: str = None

    def setup(self):
        if not self.exists:
            create_users_data_dir(strict=False)
            create_user_dir(self.username, strict=True)
            create_new_user_files(self.username)
        else:
            check_user_files(self.username)

    @property
    def exists(self):
        return user_exists(self.username)

    def get_attempts(self):
        return read_user_file(settings.FILENAMES.ATTEMPTS, self.username)

    def get_passwords(self):
        return read_user_file(settings.FILENAMES.PASSWORDS, self.username)

    def get_alterations(self):
        return read_user_file(settings.FILENAMES.ALTERATIONS, self.username)

    def get_numbers(self):
        return read_user_file(settings.FILENAMES.NUMBERS, self.username)

    def update_password_attempts(self, attempts):
        update_attempts_file(attempts, self.username)

    def get_new_attempts(self, limit=None):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        self.num_passwords = 0

        generator = password_generator(
            common_numbers=self.get_numbers(),
            alterations=self.get_alterations(),
            raw_passwords=self.get_passwords(),
        )
        attempts = self.get_attempts()

        for password in generator(attempts, limit=limit):
            self.num_passwords += 1
            yield password
