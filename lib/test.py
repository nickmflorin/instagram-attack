from itertools import combinations


class abstract_password_generator(object):

    @classmethod
    def list_to_word(cls, letters):
        return ''.join(letters)

    @classmethod
    def all_combinations(cls, iterable):
        """
        Returns all combinations for all counts up to the length of the iterable.

        Usage:
        >>> value = ['a', 'b', 'c']
        >>> all_combinations(value)
        >>> [('a', ), ('b', ), ('c', ), ('a', 'b'), ('a', 'c'), ...]
        """
        all_combos = []
        for i in range(len(iterable) + 1):
            combos = combinations(iterable, i + 1)
            all_combos.extend(combos)
        return all_combos

    @classmethod
    def mutate_chars_at_indices(cls, word, char, *args):
        # Skips First Letter
        altered = list(word)

        # Shouldn't hit exception here but just in case.
        for ind in args:
            try:
                altered[ind] = char
            except IndexError:
                continue
        return cls.list_to_word(altered)

    def capitalize_at_indices(self, word, *indices):
        word = word.lower()
        altered = list(word)
        for ind in indices:
            try:
                altered[ind] = altered[ind].upper()
            except IndexError:
                continue
        return self.list_to_word(altered)


class character_replacement_generator(abstract_password_generator):

    COMMON_CHAR_REPLACEMENTS = {
        'i': ('1', '!'),
        'a': ('3', '@'),
    }

    @classmethod
    def gen(cls, word):
        alterations = []
        for char, new_chars in cls.COMMON_CHAR_REPLACEMENTS.items():
            altered = cls.replace_with_chars(word, char, new_chars)
            alterations.extend(altered)
        return alterations

    @classmethod
    def find_char_indices(cls, word, char):
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

    @classmethod
    def replace_with_chars(cls, word, char, char_set, combo=True):
        """
        Given a character to replace and a series or single character, returns
        all possible words with that character replaced by all the characters
        in the series.

        Usage:
        >>> word = "apple"
        >>> alterations = alterations_replacing_character(word, 'p', ('1', '5'))
        >>> ['a1ple', 'ap1le', 'a11le', 'a5ple', 'ap5le', 'a55le', 'a51le', ...]
        """
        count = 0
        alterations = []

        # Replacing a single character.
        if combo:
            all_char_combos = cls.all_combinations(char_set)
            for combo in all_char_combos:
                alterations.extend(cls.replace_with_chars(word, char, combo, combo=False))
        else:
            for new_char in char_set:
                alterations.extend(cls.replace_with_char(word, char, new_char))
            # Have to iterate over alterations now
        # while count < len(char_set):
        #     replacement = char_set[count]
        #     if not alterations:
        #         alterations = cls.replace_with_char(word, char, replacement)
        #     else:
        #         for i in range(len(alterations)):
        #             # The character can not be in the alteration if all instances
        #             # were replaced with the new characters.
        #             if char in alterations[i]:
        #                 altered = cls.replace_with_char(alterations[i], char, replacement)
        #                 alterations.extend(altered)
        #     count += 1
        return alterations

    @classmethod
    def replace_with_char(cls, word, char, new_char):
        """
        Given a character to replace and a replacement, returns all different
        formattions of the word with the character(s) in the word replaced with
        the new character.

        Ignores the first character in the word.

        Usage:
        >>> word = "apple"
        >>> alterations = alterations_replacing_character(word, 'p', '1')
        >>> ['a1ple', 'ap1le', 'a11le']

        TODO
        ---
        Maybe add a limit for how many different formations of the same character
        we replace, for words that might have high frequencies of a single char.
        """
        indices = cls.find_char_indices(word, char)
        all_ind_combos = cls.all_combinations(indices)

        alterations = []
        for ind_combo in all_ind_combos:
            altered = cls.mutate_chars_at_indices(word, new_char, *ind_combo)
            alterations.append(altered)
        return alterations


word = 'Whisperingi'
found = []
combos = character_replacement_generator.gen(word)
print(combos)

assert 'Whisper!ngi' in combos
