def join(val, *gens):
    """
    Chains generators together where the values of the next generator are
    computed using the values of the first generator, and so on and so forth.

    Usage
    -----

    def gen1(val):
        for i in [1, 2]:
            yield "%s%s" % (val, i)

    def gen2(val):
        for i in ['a', 'b']:
            yield "%s%s" % (val, i)

    for ans in join('blue', gen1, gen2):
        print(ans)

    >>> bluea
    >>> bluea1
    >>> bluea2
    >>> blueb
    >>> blueb1
    >>> blueb2
    >>> blue1
    >>> blue2
    """
    for i, gen in enumerate(gens):

        def recursive_yield(index, value):
            if index < len(gens):
                if index == 0:
                    for element in gens[0](value):
                        yield element
                        yield from recursive_yield(1, element)
                else:
                    for element in gens[index](value):
                        yield element
                        yield from recursive_yield(index + 1, element)

        yield from recursive_yield(i, val)
