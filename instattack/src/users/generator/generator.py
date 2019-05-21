from collections import Counter

from .base import mutation_gen, generator_mixin
from .char_gen import char_gen
from .case_gen import case_gen

import sys


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


def join(val, *gens):
    """
    Chains generators together where the values of the next generator are
    computed using the values of the first generator, and so on and so forth.

    Usage
    -----

    def gen1(val):
        for i in [1, 2]:
            yield "%s%s" % (val, i)

    def gen2(val):
        for i in ['a', 'b']:
            yield "%s%s" % (val, i)

    for ans in join('blue', gen1, gen2):
        print(ans)

    >>> bluea
    >>> bluea1
    >>> bluea1a
    >>> bluea1b
    >>> bluea2
    >>> bluea2a
    >>> bluea2b
    >>> blueb
    >>> blueb1
    >>> blueb1a
    >>> blueb1b
    >>> blueb2
    >>> blueb2a
    >>> blueb2b
    >>> blue1
    >>> blue1a
    >>>  blue1b
    >>> blue2
    >>> blue2a
    >>> blue2b
    """
    for i, gen in enumerate(gens):

        def recursive_yield(index, val):
            if index <= len(gens):
                for element in gens[index - 1](val):
                    yield element
                    yield from recursive_yield(index + 1, element)

        yield from recursive_yield(i, val)

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

    def __init__(self, loop, user, attempts, limit=None):

        self.loop = loop
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

        for altered in self.apply_base_alterations(base):
            yield from self.apply_base_numeric_alterations(altered)

        for altered in self.apply_base_numeric_alterations(base):
            yield from self.apply_base_alterations(altered)

    def __call__(self):
        """
        TODO
        ----
        Not sure if it makes sense to apply certain generators and not others.
        combos = cls.all_combinations(cls.generators)

        Definitely have to look over this logic and make sure we are not doing
        anything completely unnecessary.
        """
        def base_generator():
            for password in self.passwords:
                yield password

                yield from join(
                    password,
                    self.apply_base_alterations,
                )
                sys.stdout.write('After Base Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

                yield from join(
                    password,
                    self.apply_base_numeric_alterations,
                )

                sys.stdout.write('After Numeric Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

                yield from join(
                    password,
                    self.apply_custom_alterations,
                )

                sys.stdout.write('After Custom Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

                yield from join(
                    password,
                    self.apply_base_alterations,
                    self.apply_base_numeric_alterations,
                )

                sys.stdout.write('After Base/Numeric Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

                yield from join(
                    password,
                    self.apply_base_alterations,
                    self.apply_base_numeric_alterations,
                    self.apply_custom_alterations,
                )

                sys.stdout.write('After Base/Numeric/Custom Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

                yield from join(
                    password,
                    self.apply_base_numeric_alterations,
                    self.apply_base_alterations,
                    self.apply_custom_alterations,
                )

                sys.stdout.write('After Numeric/Base/Custom Alterations\n')
                sys.stdout.write("%s\n" % len(self.duplicates))

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
                if self.limit and self.num_generated == self.limit:
                    break
                yield value
