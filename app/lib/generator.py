from __future__ import absolute_import
from itertools import chain


class password_generator(object):

    def __init__(self, user):
        self.user = user
        self.attempts = self.user.get_password_attempts()
        self.alterations = self.user.get_password_alterations()
        self.common_numbers = self.user.get_password_numbers()
        self.raw_passwords = self.user.get_raw_passwords()

    def __call__(self):
        return chain(
            self.yield_base_passwords(),
            self.yield_altered_passwords(),
            self.yield_numbered_passwords(),
        )

    def yield_base_passwords(self):
        for pw in self.raw_passwords:
            if pw not in self.attempts:
                yield pw

    def yield_altered_passwords(self):
        for pw in self.raw_passwords:
            for alteration in self.alterations:
                password = pw + alteration
                if password not in self.attempts:
                    yield password

    def yield_numbered_passwords(self):
        for pw in self.raw_passwords:
            for alteration in self.common_numbers:
                password = pw + alteration
                if password not in self.attempts:
                    yield password

    def yield_combined_passwords(self):
        for pw in self.raw_passwords:
            for alteration in self.alterations:
                for num_alteration in self.common_numbers:
                    option1 = pw + alteration + num_alteration
                    if option1 not in self.attempts:
                        yield option1
                    option2 = pw + num_alteration + alteration
                    if option2 not in self.attempts:
                        yield option2
