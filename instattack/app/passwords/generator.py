from collections import Counter

from instattack.config import config
from instattack.lib.utils import join

from .mutators import character_mutator, additive_mutator

from .utils import autogenerate_birthdays


class abstract_password_gen(object):

    def __init__(self, user, attempts, limit=None):
        self.limit = limit
        self.user = user

        self.passwords = [x.lower() for x in user.get_passwords()]
        self.alterations = [x.lower() for x in user.get_alterations()]
        self.numerics = user.get_numerics()
        self.attempts = attempts

        self.num_generated = 0
        self.counter = Counter()

    @property
    def duplicates(self):
        duplicates = {}
        for pw, count in self.counter.items():
            if count > 1:
                duplicates[pw] = count
        return duplicates

    def safe_yield(self, iterable):
        for value in iterable:

            if value in self.attempts:
                continue

            if value in self.counter:
                self.counter[value] += 1
                continue

            self.counter[value] += 1
            self.num_generated += 1
            yield value

            if self.limit and self.num_generated == self.limit:
                break


class password_gen(abstract_password_gen):
    """
    TODO
    ----
    Start warning if we are creating duplicate password attempts based on
    usage of the generators.

    NOTE:
    ----
    We can only check attempts at the top point in password_generator,
    otherwise, we could be discarding password alterations that would not be
    in the previous attempts after additional alterations performed.
    """

    def __init__(self, *args, **kwargs):
        super(password_gen, self).__init__(*args, **kwargs)
        if config['login']['passwords']['generator']['numerics']['birthday']['provided']:
            if self.user.birthday:
                autogenerate_birthdays(self.user, self.numerics)

    def apply_base_alterations(self, base):
        generate_alterations = additive_mutator(base, mode='alterations')

        for alteration in self.alterations:
            yield from generate_alterations(alteration)

    def apply_base_numeric_alterations(self, base):
        generate_numerics = additive_mutator(base, mode='numerics')

        for numeric in self.numerics:
            yield from generate_numerics(numeric)

    def apply_character_alterations(self, base):
        generate_custom = character_mutator(base)
        yield from generate_custom()

    def __call__(self):
        """
        TODO
        ----
        Not sure if it makes sense to apply certain generators and not others.
        combos = cls.all_combinations(cls.generators)

        Definitely have to look over this logic and make sure we are not doing
        anything completely unnecessary.

        IMPORTANT
        --------
        What we should really do is separatate the alterations into components
        in an iterable, [Caitlin, 083801331, Blue], and then just apply the
        custom alterations to the primary component, and use combinatorics to
        generate passwords.
        """
        def base_generator():
            for password in self.passwords:
                yield password

                # Applies each generator on it's own and in tandem with previous
                # generator,
                yield from join(
                    password,
                    self.apply_base_alterations,
                    self.apply_base_numeric_alterations,
                    self.apply_character_alterations,
                )

        yield from self.safe_yield(base_generator())
        print(
            f'There Were {len(self.duplicates)} '
            'Duplicates Removed from Generated Passwords'
        )
