import asyncio

from instattack.logger import AppLogger

from .base import mutation_gen

from .char_gen import char_gen
from .case_gen import case_gen


log = AppLogger(__file__)


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
    async def __call__(self, numeric):
        # Skipping for now to make faster
        # yield self.numeric_before(word, numeric)
        yield self.numeric_after(numeric)

    def numeric_before(self, numeric):
        return "%s%s" % (numeric, self.word)

    def numeric_after(self, numeric):
        return "%s%s" % (self.word, numeric)


class alteration_gen(mutation_gen):

    async def __call__(self, alteration):
        # Skipping for now to make faster
        # yield self.alteration_before(word, numeric)
        yield self.alteration_after(alteration)

    def alteration_before(self, alteration):
        return "%s%s" % (alteration, self.word)

    def alteration_after(self, alteration):
        return "%s%s" % (self.word, alteration)


class custom_gen(mutation_gen):
    """
    Custom alterations that are not necessarily defined by values in the
    alterations or common numbers text files.d
    """
    generators = [
        case_gen,
        char_gen,
    ]

    async def __call__(self):
        """
        Applies generators alone and in tandem with one another.
        """
        combos = self.all_combinations(self.generators)
        for combo in combos:
            for gen in combo:
                initialized = gen(self.word)
                async for item in initialized():
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

    def __init__(self, loop, user):
        self.user = user
        self.loop = loop
        self.duplicates = []

    async def __call__(self):
        # Not sure if it makes sense to apply certain generators and not others.
        # combos = cls.all_combinations(cls.generators)
        # Definitely have to look over this logic and make sure we are not doing
        # anything completely unnecessary.
        self.attempts = await self.user.get_attempts()
        self.generated = []
        self.duplicates = []

        async for password in self.safe_yield(self.user.get_passwords):
            yield self.yield_with(password)

            # Cover alterations and additions to base password
            async for alteration in self.user.get_alterations():
                async for altered in self.safe_yield(
                        alteration_gen(password), alteration):
                    yield self.yield_with(altered)

            async for num_alteration in self.user.get_numerics():
                async for altered in self.safe_yield(
                        numeric_gen(password), num_alteration):
                    yield self.yield_with(altered)

            async for custom_alteration in self.safe_yield(custom_gen(password)):
                yield self.yield_with(custom_alteration)

                # Cover alterations and additions to custom altered passwords
                async for alteration in self.user.get_alterations():
                    async for altered in self.safe_yield(
                            alteration_gen(custom_alteration), alteration):
                        yield self.yield_with(altered)

                async for num_alteration in self.user.get_numerics():
                    async for altered in self.safe_yield(
                            numeric_gen(custom_alteration), num_alteration):
                        yield self.yield_with(altered)

        log.info(f'Generated {len(self.generated)} Passwords')
        if len(self.duplicates):
            log.error(f'There Were {len(self.duplicates)} Generated Duplicates')

    def yield_with(self, value):
        self.generated.append(value)
        return value

    def safe_to_yield(self, val):
        if val in self.attempts:
            return False
        elif val in self.generated:
            # Don't log for each one, this is bound to happen a lot, but we want
            # to know how often it is happening.
            self.duplicates.append(val)
            return False
        return True

    async def safe_yield(self, gen, *args):
        async for value in gen(*args):
            if self.safe_to_yield(value):
                yield value
