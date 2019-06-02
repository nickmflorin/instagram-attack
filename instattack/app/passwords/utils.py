from itertools import combinations


def list_to_word(letters):
    return ''.join(letters)


def mutate_char_at_index(word, ind, char):

    word = "%s" % word
    altered = list(word)
    altered[ind] = char
    return list_to_word(altered)


def capitalize_at_indices(word, *indices):

    word = "%s" % word
    word = word.lower()
    altered = list(word)

    for ind in indices:
        try:
            altered[ind] = altered[ind].upper()
        except IndexError:
            continue
    return list_to_word(altered)


def find_indices_with_char(word, char):
    """
    Returns a list of indices where a given character exists in a word.

    >>> find_indices_with_char('applep', 'p')
    >>> [1, 2, 5]
    """
    indices = []
    word = "%s" % word

    def evaluate(c):
        if c.lower() == char.lower():
            return True
        return False

    # We might want to limit this to everything except the first char?
    unique_chars = list(set(word))
    if char in unique_chars:
        where_present = [evaluate(c) for c in word]
        indices = [i for i, x in enumerate(where_present) if x]
    return indices


def flatten_replacements(replacements):
    """
    Flattens a series replacements into an iterable of flattened replacement
    tuples.
    """
    flattened = []
    for replacement in replacements:
        flattened.append(flatten_replacement(replacement))
    return flattened


def flatten_replacement(replacement):
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


def all_combinations(iterable, choose=None):
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


def autogenerate_birthdays(user, numerics):
    """
    [x] TODO:
    --------
    Also have to make applicable and usable for year-year case.
    """
    if not user.birthday:
        raise RuntimeError(
            'User must have birthday to autogenerate birthday alterations.')

    month = "%s" % int(user.birthday.month)
    year = "%s" % int(user.birthday.year)
    day = "%s" % int(user.birthday.day)

    def two_digit_alterations(value):
        if len(value) == 2:
            return [value]
        else:
            return [
                value,
                "0%s" % value,
            ]

    day_alterations = two_digit_alterations(day)
    month_alterations = two_digit_alterations(month)
    year_alterations = [year[-2:], year]

    def generate_birthdays():
        for month in month_alterations:
            yield month
            for day in day_alterations:
                yield day
                yield "%s%s" % (month, day)
                for year in year_alterations:
                    yield "%s%s%s" % (month, day, year)

    for bday_alteration in generate_birthdays():
        if bday_alteration not in numerics:
            numerics.append(bday_alteration)
