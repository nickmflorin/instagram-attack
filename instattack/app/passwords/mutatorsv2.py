from instattack.config import config

from .utils import capitalize_at_indices, all_combinations


class mutator_v2(object):

    def __init__(self, spec):
        self.spec = spec
        self.Config = config['login']['passwords']['generator']
        self.generated = []

    def safe_yield(self, iterable):
        for item in iterable:
            if item not in self.generated:
                self.generated.append(item)
                yield item


class case_mutator_v2(mutator_v2):

    def __call__(self, *args):
        for item in self.safe_yield(self.base_generator(*args)):
            self.spec.mutations.append(item)

    def base_generator(self):
        """
        TODO
        ----
        Add setting for the maximum length of the word to make the entire
        thing uppercase.
        """
        yield self.base.lower()

        # Move Threshold to constants or Config
        THRESHOLD = 3
        if len(self.base) <= THRESHOLD:
            yield self.base.upper()

        for index_set in self.Config['capitalize_at_indices']:
            if type(index_set) is int:
                index_set = (index_set, )

            yield capitalize_at_indices(self.base, *index_set)


class additive_mutator_v2(mutator_v2):

    def __init__(self, *args, mode='alterations'):
        super(additive_mutator_v2, self).__init__(*args)
        self.mode = mode

    def __call__(self, additive):
        if self.Config[self.mode]['before']:
            self.alteration_before(additive)
        if self.Config[self.mode]['after']:
            self.alteration_after(additive)

    def alteration_before(self, value):
        self.spec.before(value)

        # This can lead to duplicates if alterations have special characters
        if self.mode == 'alteration':
            alteration_mutator = character_mutator_v2(value)
            for altered in alteration_mutator():
                self.spec.before(altered)

    def alteration_after(self, value):
        self.spec.after(value)

        # This can lead to duplicates if alterations have special characters
        if self.mode == 'alteration':
            alteration_mutator = character_mutator_v2(value)
            for altered in alteration_mutator():
                self.spec.after(altered)


class character_mutator_v2(mutator_v2):
    """
    Custom alterations that are not necessarily defined by values in the
    alterations or common numbers text files.d
    """
    generators = [
        case_mutator_v2,
        # char_mutator_v2,
    ]

    def __init__(self, spec):
        self.spec = spec

    def base_generator(self):
        """
        Applies generators alone and in tandem with one another.
        """
        combos = all_combinations(self.generators)
        for combo in combos:
            for gen in combo:
                initialized = gen(self)
                for item in initialized():
                    self.spec.mutators.append(item)
