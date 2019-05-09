from lib import AppLogger

from .base import abstract_gen

from .char_replacement import char_gen
from .case_alteration import case_gen


log = AppLogger(__file__)


class base_combination_generator(abstract_gen):
    """
    TODO
    ----

    Implement.
    This will not be using generators but will use the end product because
    we will want to try to combine certain shorter passwords that we have
    tried or are the originals.
    """

    def gen(self, word):
        pass


class numeric_gen(abstract_gen):
    """
    TODO:
    ----

    We are eventually going to want to try additional variations of the
    numbers, which might require not using generators and combining numbers
    with previous number sequences.
    """
    @classmethod
    async def gen(self, word, numeric):
        # Skipping for now to make faster
        # yield self.numeric_before(word, numeric)
        yield self.numeric_after(word, numeric)

    def numeric_before(self, word, numeric):
        return "%s%s" % (numeric, word)

    def numeric_after(self, word, numeric):
        return "%s%s" % (word, numeric)


class alteration_gen(abstract_gen):

    @classmethod
    async def gen(cls, word, alteration):
        # Skipping for now to make faster
        # yield self.alteration_before(word, numeric)
        yield cls.alteration_after(word, alteration)

    def alteration_before(cls, word, alteration):
        return "%s%s" % (alteration, word)

    def alteration_after(cls, word, alteration):
        return "%s%s" % (word, alteration)


class custom_gen(abstract_gen):
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

    @classmethod
    async def gen(cls, word):
        combos = cls.all_combinations(cls.generators)
        for combo in combos:
            for gen in combo:
                yield gen.gen(word)


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

    def __init__(self, alterations=None, numerics=None, raw=None, limit=None):
        self.alterations = alterations or []
        self.numerics = numerics or []
        self.raw = raw or []
        self.attempts = []

        self.count = 0
        self.limit = limit

    @property
    def safe_to_yield(self):
        if not self.limit or self.count < self.limit:
            return True
        return False

    async def safe_yield(self, gen):
        while self.safe_to_yield:
            try:
                val = await gen.__anext__()
                if val not in self.attempts:
                    yield val
                    self.count += 1
                else:
                    log.warning('Found duplicate generated password %s.' % val)
            except StopAsyncIteration:
                break

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
