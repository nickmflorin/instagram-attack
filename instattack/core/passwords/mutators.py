from itertools import product
from instattack import settings

from .utils import (
    find_indices_with_char, mutate_char_at_index, flatten_replacements,
    capitalize_at_indices, all_combinations)


class mutator(object):

    def __init__(self, base):
        self.base = base
        self.Config = settings.login.passwords.generator
        self.generated = []

    def __call__(self, *args):
        yield from self.safe_yield(self.base_generator(*args))

    def safe_yield(self, iterable):
        for item in iterable:
            if item not in self.generated:
                self.generated.append(item)
                yield item


class case_mutator(mutator):

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


class char_mutator(mutator):
    """
    Terminology
    -----------
    (1) replacement: (index, (char1, char2, char3, ))

        Tuple defining an index in a word and the characters that we want to replace
        at that index.

        (1a) replacements: [replacement]

             Series of replacement tuples identifying each unique index and the
             characters to replace at that index.

             >>> replacements = [replacement]
             >>> replacements = [
                    (1, ('b', 'x')),
                    (2, ('b', 'x')),
                    (5, ('b', 'x'))
                 ]

        (1b) flat replacement: [(index, char1), (index, char2)] = [mutation]

             Iterable of tuples where each tuple defines the replacement index
             and each different character in the character set.

    (2) mutation: (index, new_char)

        Tuple defining an index in a word and a character to replace at that
        index.  When used in a series, the indices must be unique.

        (2a) mutations: [mutation]

            Series of mutations where each index of each mutation in the series
            is unique.

            >>> [(1, 'b'), (2, 'b'), (5, 'x')]
    """

    def base_generator(self):
        for char, new_chars in settings.COMMON_CHAR_REPLACEMENTS.items():
            altered = self.replace_character(char, new_chars)
            for alteration in altered:
                yield alteration

    def replace_character(self, char, new_chars):
        """
        Given a character to replace and a series or single character, returns
        all possible words with that character replaced by all the characters
        in the series.

        Usage:
        >>> word = "apple"
        >>> alterations = alterations_replacing_character(word, 'p', ('1', '5'))
        >>> ['a1ple', 'ap1le', 'a11le', 'a5ple', 'ap5le', 'a55le', 'a51le', ...]

        TODO
        ---
        Maybe add a limit for how many different formations of the same character
        we replace, for words that might have high frequencies of a single char.
        """
        alterations = []
        for mutations in self.get_mutations(char, new_chars):
            altered = self.apply_mutations(mutations)
            alterations.append(altered)
        return alterations

    def apply_mutations(self, mutations):
        """
        [!] IMPORTANT
        -------------
        This is okay for now, since we are not including alterations before the
        word, but we cannot cut it off as self.base[1:-1] because of alterations
        at the end of the word.  What we need to do is start segmenting the
        altered passwords so we are aware which is the core part:

        >>> ({'value': '!', 'type': 'alteration'}), ({'value': 'pw', 'type': 'base'})
        """
        word = self.base[1:]
        for mut in mutations:
            word = mutate_char_at_index(word, *mut)
        return self.base[0] + word + self.base[-1]

    def get_mutations(self, char, new_chars):
        """
        Returns a series of mutations for a given word, character to replace
        and series of new characters.

        >>> get_mutations('applep', 'p', ('b', 'x'))
        >>> [
        >>>     ((1, 'b'), ),
        >>>     ((1, 'x'), ),
        >>>     ((2, 'b'), ),
        >>>        ...
        >>>     ((1, 'b'), (2, 'x')),
        >>>     ((1, 'b'), (2, 'b'), (5, 'b')),
        >>>        ...
        >>> ]
        """
        all_mutations = []

        replacement_combos = self.get_replacement_combinations(char, new_chars)
        for replacements in replacement_combos:
            # The result of flatten_replacements will be something along the lines
            # of:
            # >>> [[(1, 'b'), (1, 'x')], [(2, 'b'), (2, 'x')]]
            flat = flatten_replacements(replacements)
            # Find each different set of replacements with the index for each
            # replacement in the set being unique.  The result will be something
            # along the lines of:
            # >>> [(1, 'b'), (2, 'b'), (5, 'b')]
            mutations = list(product(*flat))
            all_mutations.extend(mutations)
        return all_mutations

    def get_replacements(self, char, new_chars):
        """
        Given a word, a character in the word and a set of new characters,
        returns an iterable of tuples (index, new_chars), where index refers
        to the indices where the character exists.

        >>> get_new_chars_per_index('applep', 'p', ('b', 'x'))
        >>> [(1, ('b', 'x')), (2, ('b', 'x')), (5, ('b', 'x'))]
        """
        mutations_by_index = []
        indices = find_indices_with_char(self.base, char)
        for ind in indices:
            mutations_by_index.append((ind, (new_chars)))
        return mutations_by_index

    def get_replacement_combinations(self, char, new_chars):
        """
        Get all combinations replacements for a given word, character in the
        word and set of new characters.

        >>> get_replacement_combinations('applep', 'p', ('b', 'x'))
        >>> [
        >>>    ((1, ('b', 'x')),)
        >>>    ((2, ('b', 'x')),)
        >>>    ((5, ('b', 'x')),)
        >>>    ((1, ('b', 'x')), (2, ('b', 'x')))
        >>>    ((1, ('b', 'x')), (5, ('b', 'x')))
        >>>    ((2, ('b', 'x')), (5, ('b', 'x')))
        >>>    ((1, ('b', 'x')), (2, ('b', 'x')), (5, ('b', 'x')))
        >>> ]
        """
        replacements = self.get_replacements(char, new_chars)
        return all_combinations(replacements)


class additive_mutator(mutator):
    """
    TODO:
    ----
    We are currently using this for both numerics and general alpha numeric
    alterations.

    We are eventually going to want to try additional variations of the
    numbers, which might require not using generators and combining numbers
    with previous number sequences.
    """

    def __init__(self, *args, mode='alterations'):
        super(additive_mutator, self).__init__(*args)
        self.mode = mode

    def base_generator(self, additive):
        if self.Config[self.mode]['before']:
            yield from self.alteration_before(additive)
        if self.Config[self.mode]['after']:
            yield from self.alteration_after(additive)

    def after(self, value):
        return "%s%s" % (self.base, value)

    def before(self, value):
        return "%s%s" % (value, self.base)

    def alteration_before(self, value):
        yield self.before(value)
        if self.mode == 'alteration':

            # This can lead to duplicates if alterations have special characters
            alteration_mutator = character_mutator(value)
            for altered in alteration_mutator():
                yield self.before(altered)

    def alteration_after(self, value):
        yield self.after(value)
        if self.mode == 'alteration':

            # This can lead to duplicates if alterations have special characters
            alteration_mutator = character_mutator(value)
            for altered in alteration_mutator():
                yield self.after(altered)


class character_mutator(mutator):
    """
    Custom alterations that are not necessarily defined by values in the
    alterations or common numbers text files.d
    """
    generators = [
        case_mutator,
        char_mutator,
    ]

    def base_generator(self):
        """
        Applies generators alone and in tandem with one another.
        """
        combos = all_combinations(self.generators)
        for combo in combos:
            for gen in combo:
                initialized = gen(self.base)
                for item in initialized():
                    yield item
