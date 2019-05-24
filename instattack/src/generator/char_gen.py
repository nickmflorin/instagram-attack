from itertools import product

from .base import mutation_gen


class char_gen(mutation_gen):
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

    def __call__(self):
        for char, new_chars in self.COMMON_CHAR_REPLACEMENTS.items():
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
            flat = self.flatten_replacements(replacements)
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
        indices = self.find_indices_with_char(char)
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
        return self.all_combinations(replacements)

    def flatten_replacements(self, replacements):
        """
        Flattens a series replacements into an iterable of flattened replacement
        tuples.
        """
        flattened = []
        for replacement in replacements:
            flattened.append(self.flatten_replacement(replacement))
        return flattened

    def flatten_replacement(self, replacement):
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

    def apply_mutations(self, mutations):
        word = self.base
        for mut in mutations:
            word = self.mutate_char_at_index(word, *mut)
        return word
