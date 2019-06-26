import pytest

from instattack.config.exceptions import ConfigFieldError
from instattack.config.fields import (
    DictField, ListField, SetField, PositiveIntField, BooleanField)


def test_set_field():

    field = SetField(
        foo=BooleanField(default=False),
        bar=PositiveIntField(max=10, default=5),
        booey=DictField({
            'foo': 'bar',
            'fooey': 'barz',
        })
    )


def test_list_field():

    field = ListField([
        'foo',
        'bar',
        'fooey',
    ])
    assert field.value == ['foo', 'bar', 'fooey']

    field.configure(['foo', 'bar'])
    assert field.value == ['foo', 'bar']

    # Test Non Configurable Field - Trying to configure the field should raise
    # an exception.
    field = ListField([
        'foo',
        'bar',
        'fooey',
    ], configurable=False)

    with pytest.raises(ConfigFieldError):
        field.configure(['foo', 'bar'])


def test_dict_field():

    field = DictField({
        'foo': 'bar',
        'fooey': 'barz',
    })

    # Test case insensitivity
    assert field.foo == field.FOO == 'bar'
    assert field.fooey == field.FOOEY == 'barz'

    # Test if we can configure and change a field value.
    field.configure(foo='apple')
    assert field.foo == field.FOO == 'apple'

    # Test if trying to configure a missing field raises an error and does not
    # add the field.
    with pytest.raises(ConfigFieldError):
        field.configure(bar='foo')

    # Test if accessing a missing attribute raises an exception.
    with pytest.raises(AttributeError):
        field.bar

    # Test if configuring a non-configurable instance of the field raises an
    # error.
    field = DictField(
        {
            'foo': 'bar',
            'fooey': 'barz',
        },
        configurable=False
    )
    with pytest.raises(ConfigFieldError):
        field.configure(foo='barfoo')
