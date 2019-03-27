from __future__ import absolute_import

import os
import app.settings as settings


class Users(object):

    @classmethod
    def get_or_create(cls, username):
        if not cls.exists(username):
            return User.create(username)
        return User(username)

    @classmethod
    def exists(cls, username):
        user = User(username)
        if os.path.exists(user.file_path):
            return True
        return False

    @classmethod
    def create(cls, username):
        if cls.exists(username):
            raise Exception(f"User {username} already exists.")
        cls.create_directory()
        user = User.create(username)
        return user

    @classmethod
    def create_directory(cls):
        if not os.path.exists(settings.USER_DIRECTORY):
            os.mkdir(settings.USER_DIRECTORY)


class User(object):

    def __init__(self, username):
        self.username = username

    @classmethod
    def create(cls, username):
        user = User(username)
        user.create_directory()
        user.create_password_file()
        user.create_attempts_file()
        return user

    @property
    def password_file_name(self):
        return f"{settings.PASSWORD_FILENAME}.txt"

    @property
    def attempt_file_name(self):
        return f"{settings.ATTEMPTS_FILENAME}.txt"

    @property
    def file_path(self):
        return os.path.join(settings.USER_DIRECTORY, self.username)

    @property
    def password_file_path(self):
        return os.path.join(
            self.file_path,
            self.password_file_name
        )

    @property
    def attempts_file_path(self):
        return os.path.join(
            self.file_path,
            self.attempt_file_name
        )

    def open_password_file(self, mode="w+"):
        return open(self.password_file_path, mode)

    def open_attempts_file(self, mode="w+"):
        return open(self.attempts_file_path, mode)

    def create_directory(self):
        Users.create_directory()
        if not os.path.exists(self.file_path):
            os.mkdir(self.file_path)

    def create_password_file(self):
        self.create_directory()
        if not os.path.exists(self.password_file_path):
            with open(self.password_file_path, "w+"):
                pass

    def create_attempts_file(self):
        self.create_directory()
        if not os.path.exists(self.attempts_file_path):
            with open(self.attempts_file_path, "w+"):
                pass

    def _read_lines(self, file):
        formatted = []
        lines = file.readlines()
        for line in lines:
            line = line.replace("\n", "").replace("\t", "")
            formatted.append(line)
        return formatted

    def get_raw_passwords(self):
        self.create_password_file()
        with self.open_password_file(mode='r') as file:
            return self._read_lines(file)

    def get_password_attempts(self):
        self.create_attempts_file()
        with self.open_attempts_file(mode='r') as file:
            return self._read_lines(file)

    def _write_password_attempts(self, attempts):
        with self.open_attempts_file() as file:
            for attempt in attempts:
                file.write(f"{attempt}\n")

    def clear_password_attempts(self):
        self.create_attempts_file()
        with self.open_attempts_file():
            pass

    def update_password_attempts(self, attempts):

        current = self.get_password_attempts()
        attempts = list(set(attempts))
        current = list(set(current))

        unique_attempts = [att for att in attempts if att not in current]
        print(f"Saving {len(unique_attempts)} unique additional attempts.")

        all_attempts = sorted(current + unique_attempts)

        self._write_password_attempts(all_attempts)

    def get_new_attempts(self):
        """
        For now, just returning current passwords for testing, but we will
        eventually want to generate alterations and compare to existing
        password attempts.
        """
        return self.get_raw_passwords()

    def _password_alterations(self, password):
        first_level = ['', 'a', '13579', '24680', '09', '1523', '1719', '0609',
            '0691', '0991', '36606', '3660664', '6951', '20002']
        second_level = ['!', '!!', '!!!', '@', '`', '!a', '@!', 'a@!']

        for alteration in first_level:
            pw = password + alteration
            self.password_attempt_queue.put(pw)
            yield pw
            for two_alteration in second_level:
                pw = password + alteration + two_alteration
                self.password_attempt_queue.put(pw)
                yield pw

