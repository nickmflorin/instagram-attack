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


class core_password_generator(object):
    def __init__(self, alterations=None, common_numbers=None, raw_passwords=None):
        self.alterations = alterations or []
        self.common_numbers = common_numbers or []
        self.raw_passwords = raw_passwords or []


class case_alteration_generator(abstract_password_generator):

    async def gen(self, word):
        async for case_alteration in self.alterations_of_case.gen(word):
            yield case_alteration

    async def alterations_of_case(self, word):
        # TODO: Add setting for the maximum length of the word to make the entire
        # thing uppercase.
        yield word.lower()
        yield self.capitalize_at_indices(word, 0)
        yield self.capitalize_at_indices(word, 0, 1)
        yield self.capitalize_at_indices(word, 1)


class character_replacement_generator(abstract_password_generator):

    COMMON_CHAR_REPLACEMENTS = {
        'i': ('1', '!'),
        'a': ('3', '@'),
    }

    @classmethod
    def gen(cls, word):
        # Using `Whisperingi`, we do not get `Whisper!ngi` in results...
        # See test.py
        raise Exception('This is still not working!')
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
    def replace_with_chars(cls, word, char, char_set):
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

        while count < len(char_set):
            replacement = char_set[count]
            if not alterations:
                alterations = cls.replace_with_char(word, char, replacement)
            else:
                for i in range(len(alterations)):
                    # The character can not be in the alteration if all instances
                    # were replaced with the new characters.
                    if char in alterations[i]:
                        altered = cls.replace_with_char(alterations[i], char, replacement)
                        alterations.extend(altered)
            count += 1
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


# TODO: Thsi will require not using generators at end product because we have
# to have history of words to generate combinations with.
class base_combination_generator(abstract_password_generator):

    def gen(self, word):
        pass


class base_alteration_generator(abstract_password_generator):
    """
    Generates all possible combinations of a single password given the
    different sub-generators that make up this generator.
    """

    async def gen(self, word):
        cases = case_alteration_generator()
        for case_altered in cases(word):
            yield case_altered

            # Skipping for now to make faster
            # replacements = character_replacement_generator()
            # for char_altered in replacements(case_altered):
            #     yield char_altered


class base_core_generator(core_password_generator):
    """
    Loops over all of the raw passwords and yields all of the alterations of each
    password.

    We should only check if the word is not in the attempts in the core generators
    to make logic easier in more complicated sub generators.
    """

    async def gen(self):
        generator = base_alteration_generator()
        for password in self.raw_passwords:
            for alteration in generator(password):
                yield alteration


class numeric_core_generator(core_password_generator):
    """
    TODO: We are eventually going to want to try additional variations of the
    numbers, which might require not using generators and combining numbers
    with previous number sequences.
    """

    async def gen(self, word):
        for numeric_sequence in self.common_numbers:
            yield from self.alterations_before_after(word, numeric_sequence)

    def alterations_before_after(self, word, numeric_alteration):
        yield "%s%s" % (word, numeric_alteration)

        # Skipping for now to make faster
        # yield "%s%s" % (numeric_alteration, word)


class alteration_core_generator(core_password_generator):
    """
    TODO: Right now, we are just appending these to the end of the sequence,
    but we are eventually going to want to come up with more combinations
    of doing this.
    """

    async def gen(self, word):
        async for alteration in self.alterations:
            yield from self.alterations_after_word(word, alteration)

    def alterations_after_word(self, word, alteration):
        yield "%s%s" % (word, alteration)


# Note: We can only check attempts at the top point in password_generator,
# otherwise, we could be discarding password alterations that would not be
# in the previous attempts after additional alterations performed.
class password_generator(core_password_generator):

    def __init__(self, **kwargs):
        super(password_generator, self).__init__(**kwargs)

        self.count = 0
        self.base_generator = base_core_generator(**kwargs)
        self.numeric_generator = numeric_core_generator(**kwargs)
        self.alteration_generator = alteration_core_generator(**kwargs)

    async def gen(self, attempts=None, limit=None):
        attempts = attempts or []
        self.count = 0

        def safe_to_yield():
            if not limit or self.count < limit:
                self.count += 1
                return True

        async for base_alteration in self.base_generator.gen():
            if base_alteration not in attempts:
                if not safe_to_yield():
                    return
                yield base_alteration

            async for alteration in self.alteration_generator.gen(base_alteration):
                if alteration not in attempts:
                    if not safe_to_yield():
                        return
                    yield alteration

            async for numeric_alteration in self.numeric_generator.gen(base_alteration):
                if numeric_alteration not in attempts:
                    if not safe_to_yield():
                        return
                    yield numeric_alteration

                async for num_alteration in self.alteration_generator.gen(numeric_alteration):
                    if num_alteration not in attempts:
                        if not safe_to_yield():
                            return
                        yield num_alteration
