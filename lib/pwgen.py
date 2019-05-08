from itertools import combinations


class abstract_password_generator(object):

    def list_to_word(self, letters):
        return ''.join(letters)

    def mutate_chars(self, word, char, *indices):
        # Skips First Letter
        word = word.lower()
        altered = list(word)[1:]

        # Shouldn't hit exception here but just in case.
        for ind in indices:
            try:
                altered[ind] = char
            except IndexError:
                continue
        return self.list_to_word(list(word)[0] + altered)

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

    def __call__(self, word):
        for case_alteration in self.alterations_of_case(word):
            yield case_alteration

    def alterations_of_case(self, word):
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

    def __call__(self, word):
        for char, new_chars in self.COMMON_CHAR_REPLACEMENTS.items():
            yield from self.alterations_replacing_characters(
                word, char, new_chars)

    def alterations_replacing_characters(self, word, char, new_chars):
        """
        Given a word, a character to replace and an iterable of characters to use
        in it's place, generates all possible combinations of the word with all possible
        frequencies of the `char`(s) existence in the word replaced with all
        possible combination of the new_chars.

        Usage:

        >>> word = "apple"
        >>> alterations = alterations_replacing_character(word, 'p', ('b', '3'))
        >>> ['a3ple', 'ap3le', 'a33le', 'abple', 'apble', 'abble', 'ab3le', 'a3ble']
        """
        for i, new_char in enumerate(new_chars):
            char_alterations = self.alterations_replacing_character(word, char, new_char)
            for alteration in char_alterations:
                yield alteration

                if i >= 1:
                    yield from self.alterations_replacing_character(
                        alteration, char, new_chars[i - 1])

    def alterations_replacing_character(self, word, char, new_char):
        """
        Given a character to replace and a replacement, returns all different
        formattions of the word with the character(s) in the word replaced with
        the new character.

        Ignores the first character in the word.

        Usage:
        >>> word = "apple"
        >>> alterations = alterations_replacing_character(word, 'p', '1')
        >>> ['a1ple', 'ap1le', 'a11le']
        """
        if char in word[1:]:
            where_present = [True if (c == char or c.upper() == char) else False for c in word[1:]]
            indices = [i for i in range(len(where_present)) if where_present[i]]

            count = word[1:].count(char)
            for i in range(count + 1):
                combos = combinations(indices, i + 1)
                for combo in combos:
                    yield self.mutate_chars(word, new_char, combos)


# TODO: Thsi will require not using generators at end product because we have
# to have history of words to generate combinations with.
class base_combination_generator(abstract_password_generator):

    def __call__(self, word):
        pass


class base_alteration_generator(abstract_password_generator):
    """
    Generates all possible combinations of a single password given the
    different sub-generators that make up this generator.
    """

    def __call__(self, word):
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

    def __call__(self):
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

    def __call__(self, word):
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

    def __call__(self, word):
        for alteration in self.alterations:
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

    def __call__(self, attempts=None, limit=None):
        attempts = attempts or []
        self.count = 0

        def safe_to_yield():
            if not limit or self.count < limit:
                self.count += 1
                return True

        for base_alteration in self.base_generator():
            if base_alteration not in attempts:
                if not safe_to_yield():
                    return
                yield base_alteration

            for alteration in self.alteration_generator(base_alteration):
                if alteration not in attempts:
                    if not safe_to_yield():
                        return
                    yield alteration

            for numeric_alteration in self.numeric_generator(base_alteration):
                if numeric_alteration not in attempts:
                        if not safe_to_yield():
                            return
                        yield numeric_alteration

                for num_alteration in self.alteration_generator(numeric_alteration):
                    if num_alteration not in attempts:
                        if not safe_to_yield():
                            return
                        yield num_alteration
