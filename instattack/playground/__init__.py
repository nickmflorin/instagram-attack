"""
This module is only for developer environments.

Creating a sub-module where we can store test code, duplicate and modified versions
of existing code and explore programming possibilities is a crucial part of
this project.

It is in this module where we play around with certain packages, code and
ideas, not being in the Cement app framework but still having access to the
components that make up the instattack app.
"""


def playground():

    class ConditionalString(str):

        def __new__(cls, *args):
            value = str.__new__(cls, args[-1])
            setattr(value, 'conditionals', args[:-1])

    s = ConditionalString('field', 'for field {field}')
    print(s)

    # EXCEEDS_MAX = "The value " + Conditional('field', 'for field {field}') + Conditional('value', 'max', 'exceeds the maximum ({value} > {max})') + '.'
