from itertools import combinations


class mutation_gen(object):

    def __init__(self, word):
        self.word = word

    def list_to_word(self, letters):
        return ''.join(letters)

    def mutate_char_at_index(self, word, ind, char):
        altered = list(word)
        altered[ind] = char
        return self.list_to_word(altered)

    def all_combinations(self, iterable, choose=None):
        """
        Returns all combinations for all counts up to the length of the iterable.

        Usage:
        >>> value = ['a', 'b', 'c']
        >>> all_combinations(value)
        >>> [('a', ), ('b', ), ('c', ), ('a', 'b'), ('a', 'c'), ...]
        """
        all_combos = []
        limit = choose or len(iterable)
        for i in range(limit + 1):
            combos = combinations(iterable, i + 1)
            all_combos.extend(combos)
        return all_combos

    def find_indices_with_char(self, char):
        """
        Returns a list of indices where a given character exists in a word.

        >>> find_indices_with_char('applep', 'p')
        >>> [1, 2, 5]
        """
        indices = []

        def evaluate(c):
            if c.lower() == char.lower():
                return True
            return False

        # We might want to limit this to everything except the first char?
        unique_chars = list(set(self.word))
        if char in unique_chars:
            where_present = [evaluate(c) for c in self.word]
            indices = [i for i, x in enumerate(where_present) if x]
        return indices

    def capitalize_at_indices(self, *indices):
        word = self.word.lower()
        altered = list(word)
        for ind in indices:
            try:
                altered[ind] = altered[ind].upper()
            except IndexError:
                continue
        return self.list_to_word(altered)
