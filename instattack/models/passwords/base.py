from itertools import combinations


class abstract_gen(object):

    @classmethod
    def list_to_word(cls, letters):
        return ''.join(letters)

    @classmethod
    def all_combinations(cls, iterable, choose=None):
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

    @classmethod
    def find_indices_with_char(cls, word, char):
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

        unique_chars = list(set(word))
        if char in unique_chars:
            where_present = [evaluate(c) for c in word]
            indices = [i for i, x in enumerate(where_present) if x]
        return indices

    def capitalize_at_indices(self, word, *indices):
        word = word.lower()
        altered = list(word)
        for ind in indices:
            try:
                altered[ind] = altered[ind].upper()
            except IndexError:
                continue
        return self.list_to_word(altered)
