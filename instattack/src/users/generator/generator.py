from itertools import chain, islice

from instattack import logger

from .base import mutation_gen
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


class base_combination_generator(mutation_gen):
    """
    TODO
    ----

    Implement.
    This will not be using generators but will use the end product because
    we will want to try to combine certain shorter passwords that we have
    tried or are the originals.
    """
    pass


class numeric_gen(mutation_gen):
    """
    TODO:
    ----

    We are eventually going to want to try additional variations of the
    numbers, which might require not using generators and combining numbers
    with previous number sequences.
    """

    def __call__(self, numeric):
        # Skipping for now to make faster
        # yield self.numeric_before(word, numeric)
        yield self.numeric_after(numeric)

    def numeric_before(self, numeric):
        return "%s%s" % (numeric, self.base)

    def numeric_after(self, numeric):
        return "%s%s" % (self.base, numeric)


class alteration_gen(mutation_gen):

    def __call__(self, alteration):
        # Skipping for now to make faster
        # yield self.alteration_before(word, numeric)
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


class password_gen(object):
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
    generators = [
        numeric_gen,
        alteration_gen,
        custom_gen,
    ]

    def __init__(self, loop, user, attempts, limit=None):

        self.loop = loop
        self.limit = limit

        self.passwords = user.get_passwords()
        self.alterations = user.get_alterations()
        self.numerics = user.get_numerics()
        self.attempts = attempts

        self.generated = []
        self.duplicates = []

    def apply_base_alterations(self, base):
        generate_alterations = alteration_gen(base)

        for alteration in self.alterations:
            for altered in generate_alterations(alteration):
                yield altered

    def apply_base_numeric_alterations(self, base):
        generate_numerics = numeric_gen(base)

        for numeric in self.numerics:
            for altered in generate_numerics(numeric):
                yield altered

    def apply_custom_alterations(self, base):
        generate_custom = custom_gen(base)

        for altered in generate_custom():
            yield altered

    def apply_combined_alterations(self, base):

        for numeric in self.numerics:
            yield from self.apply_base_alterations(numeric)

        for alteration in self.alterations:
            yield from self.apply_base_numeric_alterations(alteration)

    def __call__(self):
        """
        TODO
        ----
        Not sure if it makes sense to apply certain generators and not others.
        combos = cls.all_combinations(cls.generators)

        Definitely have to look over this logic and make sure we are not doing
        anything completely unnecessary.
        """
        log = logger.get_async("Generating Passwords")

        def base_generator():
            for password in self.passwords:
                yield password

                for value in chain(
                    self.apply_base_alterations(password),
                    self.apply_base_numeric_alterations(password),
                    self.apply_combined_alterations(password),
                    self.apply_custom_alterations(password)
                ):
                    yield value
                    yield from chain(
                        self.apply_base_alterations(value),
                        self.apply_base_numeric_alterations(value),
                        self.apply_combined_alterations(value),
                        self.apply_custom_alterations(value)
                    )

        yield from self.safe_yield(base_generator())

        if len(self.duplicates) != 0:
            log.error(f'There Were {len(self.duplicates)} Generated Duplicates')

    def safe_to_yield(self, val):
        if val in self.attempts:
            return False
        elif val in self.generated:
            # Don't log for each one, this is bound to happen a lot, but we want
            # to know how often it is happening.
            self.duplicates.append(val)
            return False
        return True

    def safe_yield(self, gen):
        for value in gen:
            if self.safe_to_yield(value):
                if self.limit and len(self.generated) == self.limit:
                    break
                self.generated.append(value)
                yield value
