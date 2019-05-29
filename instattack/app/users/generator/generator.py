from collections import Counter

from instattack.lib.utils import join

from .base import mutation_gen, generator_mixin
from .char_gen import char_gen
from .case_gen import case_gen


"""
TODO
----

Password Pairings
-----------------

(mer, eileen)
(mer, gins) -> Should do each one individually and combos of the two

All birthday combos with year
-> 01, 02, 03, 04, 05, 06, ... for month, combined with all digits and years

Limit
-----
Cannot figure out why the hard limit and shutting down async gens is not enough
to ensure that the limit is not consistent with how many passwords are generated.
There always seems to be an extra couple that are generated.
"""


class alteration_gen(mutation_gen):
    """
    TODO:
    ----
    We are currently using this for both numerics and general alpha numeric
    alterations.

    We are eventually going to want to try additional variations of the
    numbers, which might require not using generators and combining numbers
    with previous number sequences.
    """

    def __call__(self, alteration):
        # Skipping for now to make faster
        yield self.alteration_before(alteration)
        yield self.alteration_after(alteration)

    def alteration_before(self, alteration):
        return "%s%s" % (alteration, self.base)

    def alteration_after(self, alteration):
        return "%s%s" % (self.base, alteration)


class custom_gen(mutation_gen):
    """
    Custom alterations that are not necessarily defined by values in the
    alterations or common numbers text files.d
    """
    generators = [
        case_gen,
        char_gen,
    ]

    def __call__(self):
        """
        Applies generators alone and in tandem with one another.
        """
        combos = self.all_combinations(self.generators)
        for combo in combos:
            for gen in combo:
                initialized = gen(self.base)
                for item in initialized():
                    yield item


class password_gen(generator_mixin):
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

    def __init__(self, user, attempts, limit=None):
        self.limit = limit

        self.passwords = user.get_passwords()
        self.alterations = user.get_alterations()
        self.numerics = user.get_numerics()
        self.attempts = attempts

        self.num_generated = 0
        self.counter = Counter()

    def apply_base_alterations(self, base):
        generate_alterations = alteration_gen(base)

        for alteration in self.alterations:
            yield from generate_alterations(alteration)

    def apply_base_numeric_alterations(self, base):
        generate_numerics = alteration_gen(base)

        for numeric in self.numerics:
            yield from generate_numerics(numeric)

    def apply_custom_alterations(self, base):
        generate_custom = custom_gen(base)
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
                    self.apply_custom_alterations,
                )

                # prev_duplicate_count = len(self.duplicates)
                # prev_count = len(self.counter)

                # sys.stdout.write('Duplicates After Base - Numeric - Custom Alterations\n')
                # sys.stdout.write("%s\n" % prev_duplicate_count)
                # sys.stdout.write('Total After Base - Numeric - Custom Alterations\n')
                # sys.stdout.write("%s\n" % prev_count)

                # This does not add anything extra to the pool!
                # yield from join(
                #     password,
                #     self.apply_base_alterations,
                #     self.apply_base_numeric_alterations,
                # )

                # prev_duplicate_count = len(self.duplicates) - prev_duplicate_count
                # prev_count = len(self.counter) - prev_count

                # sys.stdout.write('Duplicates After Base - Numeric Alterations\n')
                # sys.stdout.write("%s\n" % prev_duplicate_count)
                # sys.stdout.write('Total After Base - Numeric Alterations\n')
                # sys.stdout.write("%s\n" % prev_count)

        yield from self.safe_yield(base_generator())

    @property
    def duplicates(self):
        duplicates = {}
        for pw, count in self.counter.items():
            if count > 1:
                duplicates[pw] = count
        return duplicates

    def with_yield(self, val):
        if val in self.attempts:
            return False

        if val in self.counter:
            self.counter[val] += 1
            return False

        self.num_generated += 1
        self.counter[val] += 1
        return True

    def safe_yield(self, gen):
        for value in gen:
            if self.with_yield(value):
                yield value
                if self.limit and self.num_generated == self.limit:
                    break