from __future__ import absolute_import

from itertools import combinations


class abstract_password_generator(object):
    pass


class core_password_generator(object):
    def __init__(self, alterations=None, common_numbers=None, raw_passwords=None):

        self.alterations = alterations
        self.common_numbers = common_numbers
        self.raw_passwords = raw_passwords


class case_alteration_generator(abstract_password_generator):

    def __call__(self, word):
        for case_alteration in self.alterations_of_case(word):
            yield case_alteration

    def alterations_of_case(self, word):
        word = word[:].lower()

        def first_char_upper(word):
            altered = list(word)
            altered = [altered[0].upper()] + altered[1:]
            return ''.join(altered)

        # This might not be totally necessary but whatever
        def second_char_upper(word):
            altered = list(word)
            altered = [altered[0]] + [altered[1].upper()] + altered[2:]
            return ''.join(altered)

        # TODO: Add setting for the maximum length of the word to make the entire
        # thing uppercase.
        yield word.lower()
        yield word.upper()
        yield first_char_upper(word)

        if len(word) >= 2:
            # Yields with just the second character uppercase and the first & second
            # character uppercased.
            yield second_char_upper(word)
            first_upper = first_char_upper(word)
            yield second_char_upper(first_upper)


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
        def mutute_characters_at_indices(word, indices, char):
            altered = list(word[1:])
            for index in indices:
                altered[index] = char
            altered.insert(0, word[0])
            altered = ''.join(altered)
            return ''.join(altered)

        if char in word[1:]:

            where_present = [True if (c == char or c.upper() == char) else False for c in word[1:]]
            indices = [i for i in range(len(where_present)) if where_present[i]]

            count = word[1:].count(char)

            for i in range(count + 1):
                combos = combinations(indices, i + 1)
                for combo in combos:
                    altered = mutute_characters_at_indices(word, combo, new_char)
                    yield altered


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

            replacements = character_replacement_generator()
            for char_altered in replacements(case_altered):
                yield char_altered


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
        yield "%s%s" % (numeric_alteration, word)


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

    def __init__(self, user):
        self.user = user
        self.attempts = self.user.get_password_attempts()

        alterations = self.user.get_password_alterations()
        common_numbers = self.user.get_password_numbers()
        raw_passwords = self.user.get_raw_passwords()

        super(password_generator, self).__init__(
            alterations=alterations,
            common_numbers=common_numbers,
            raw_passwords=raw_passwords,
        )

        self.base_generator = base_core_generator(
            alterations=alterations,
            common_numbers=common_numbers,
            raw_passwords=raw_passwords,
        )

        self.numeric_generator = numeric_core_generator(
            alterations=alterations,
            common_numbers=common_numbers,
            raw_passwords=raw_passwords,
        )

        self.alteration_generator = alteration_core_generator(
            alterations=alterations,
            common_numbers=common_numbers,
            raw_passwords=raw_passwords,
        )

    def __call__(self):
        for base_alteration in self.base_generator():
            if base_alteration not in self.attempts:
                yield base_alteration

            for alteration in self.alteration_generator(base_alteration):
                if alteration not in self.attempts:
                    yield alteration

            for numeric_alteration in self.numeric_generator(base_alteration):
                if numeric_alteration not in self.attempts:
                    yield numeric_alteration

                for alteration in self.alteration_generator(numeric_alteration):
                    if alteration not in self.attempts:
                        yield alteration
