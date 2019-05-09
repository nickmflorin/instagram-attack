from itertools import product

from .base import abstract_gen


class char_gen(abstract_gen):
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
    COMMON_CHAR_REPLACEMENTS = {
        'i': ('1', '!'),
        'p': ('3', '@'),
    }

    @classmethod
    async def gen(cls, word):
        for char, new_chars in cls.COMMON_CHAR_REPLACEMENTS.items():
            altered = cls.replace_char_with_chars(word, char, new_chars)
            for alteration in altered:
                yield alteration

    @classmethod
    def replace_character(cls, word, char, new_chars):
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
        for mutations in cls.get_mutations(word, char, new_chars):
            altered = cls.apply_mutations(word, mutations)
            alterations.append(altered)
        return alterations

    @classmethod
    def get_mutations(cls, word, char, new_chars):
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

        replacement_combos = cls.get_replacement_combinations(word, char, new_chars)
        for replacements in replacement_combos:
            # The result of flatten_replacements will be something along the lines
            # of:
            # >>> [[(1, 'b'), (1, 'x')], [(2, 'b'), (2, 'x')]]
            flat = cls.flatten_replacements(replacements)
            # Find each different set of replacements with the index for each
            # replacement in the set being unique.  The result will be something
            # along the lines of:
            # >>> [(1, 'b'), (2, 'b'), (5, 'b')]
            mutations = list(product(*flat))
            all_mutations.extend(mutations)
        return all_mutations

    @classmethod
    def get_replacements(cls, word, char, new_chars):
        """
        Given a word, a character in the word and a set of new characters,
        returns an iterable of tuples (index, new_chars), where index refers
        to the indices where the character exists.

        >>> get_new_chars_per_index('applep', 'p', ('b', 'x'))
        >>> [(1, ('b', 'x')), (2, ('b', 'x')), (5, ('b', 'x'))]
        """
        mutations_by_index = []
        indices = cls.find_indices_with_char(word, char)
        for ind in indices:
            mutations_by_index.append((ind, (new_chars)))
        return mutations_by_index

    @classmethod
    def get_replacement_combinations(cls, word, char, new_chars):
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
        replacements = cls.get_replacements(word, char, new_chars)
        return cls.all_combinations(replacements)

    @classmethod
    def flatten_replacements(cls, replacements):
        """
        Flattens a series replacements into an iterable of flattened replacement
        tuples.
        """
        flattened = []
        for replacement in replacements:
            flattened.append(cls.flatten_replacement(replacement))
        return flattened

    @classmethod
    def flatten_replacement(cls, replacement):
        """
        Flattens a replacement (ind, (char1, char2, ...)) into an iterable
        where each iterable is defined by the replacement index with a different
        char in the replacement characters.

        >>> [(ind, char1), (ind, char2), ...]
        """
        flat_replacement = []
        for ch in replacement[1]:
            flat_replacement.append((replacement[0], ch))
        return flat_replacement

    @classmethod
    def apply_mutation(cls, word, ind, char):
        altered = list(word)
        altered[ind] = char
        return cls.list_to_word(altered)

    @classmethod
    def apply_mutations(cls, word, mutations):
        for mut in mutations:
            word = cls.apply_mutation(word, *mut)
        return word
