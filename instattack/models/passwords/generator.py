from instattack.lib import AppLogger

from .base import mutation_gen

from .char_gen import char_gen
from .case_gen import case_gen


log = AppLogger(__file__)


"""
TODO
----

Password Pairings

(mer, eileen)
(mer, gins) -> Should do each one individually and combos of the two

All birthday combos with year
-> 01, 02, 03, 04, 05, 06, ... for month, combined with all digits and years
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
    alterations or common numbers text files.

    TODO
    ----
    We might want to apply some of these generators in tandem with one another.
    We can probably do this by using the itertools.combinations() operator.
    """
    generators = [
        case_gen,
        char_gen,
    ]

    async def __call__(self):
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

    def __init__(self, user, limit=None):
        self.user = user
        self.count = 0
        self.duplicates = []
        self.limit = limit

    def yield_with(self, value):
        self.generated.append(value)
        return value

    async def __call__(self):
        # Not sure if it makes sense to apply certain generators and not others.
        # combos = cls.all_combinations(cls.generators)
        # Definitely have to look over this logic and make sure we are not doing
        # anything completely unnecessary.
        self.count = 0
        self.attempts = await self.user.get_attempts()
        self.generated = []
        self.duplicates = []

        async for password in self.user.get_passwords():
            async for alteration in self.safe_yield(custom_gen(password)):
                yield self.yield_with(alteration)

                async for alteration in self.user.get_alterations():
                    async for altered in self.safe_yield(alteration_gen(alteration), alteration):
                        yield self.yield_with(altered)

                async for num_alteration in self.user.get_numerics():
                    async for altered in self.safe_yield(numeric_gen(alteration), num_alteration):
                        yield self.yield_with(altered)

            async for user_alteration in self.user.get_alterations():
                async for altered in self.safe_yield(alteration_gen(password), user_alteration):
                    yield self.yield_with(altered)

        log.info(f'Generated {len(self.generated)} Passwords')
        log.info(f'There Were {len(self.duplicates)} Generated Duplicates')

    def safe_to_yield(self, val):
        if self.limit and not self.count < self.limit:
            return False
        elif val in self.attempts:
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
                self.count += 1

        # while self.safe_to_yield:
        #     try:
        #         val = await generator.__anext__()
        #         if val not in self.attempts:
        #             yield val
        #             self.count += 1
        #         else:
        #             log.warning('Found duplicate generated password %s.' % val)
        #     except StopAsyncIteration:
        #         break

    async def apply_alterations(self, word):
        async for alteration in self.alterations:
            gen = alteration_gen.gen(word, alteration)
            yield self.safe_yield(gen)

    async def apply_numerics(self, word):
        async for numeric in self.numerics:
            gen = numeric_gen.gen(word, numeric)
            yield self.safe_yield(gen)

    async def apply_custom(self, word):
        yield self.safe_yield(custom_gen.gen(word))

    async def gen(self, attempts=None, limit=None):
        attempts = attempts or []
        self.count = 0

        # Not sure if it makes sense to apply certain generators and not others.
        # combos = cls.all_combinations(cls.generators)
        # Definitely have to look over this logic and make sure we are not doing
        # anything completely unnecessary.
        async for password in self.raw:
            yield self.apply_custom(password)
            yield self.apply_alterations(password)
            yield self.apply_numerics(password)

            async for altered in self.apply_alterations(password):
                yield self.apply_numerics(altered)

            async for altered in self.apply_numerics(password):
                yield self.apply_custom(altered)

            async for altered in self.apply_alterations(password):
                async for altered2 in self.apply_numerics(password):
                    yield self.apply_custom(altered2)
