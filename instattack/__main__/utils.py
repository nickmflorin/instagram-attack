#!/usr/bin/env python3
import asyncio
from plumbum import cli

from instattack.logger import AppLogger


log = AppLogger(__file__)


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)


def is_numeric(value):
    try:
        float(value)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None
    else:
        try:
            return int(value)
        except ValueError:
            return float(value)
        else:
            if float(value) == int(value):
                return int(value)
            return float(value)


def parse_dict_string(value, uppercase=False):

    def evaluate_dict_value(item_value):
        numeric = is_numeric(item_value)
        if not numeric:
            if isinstance(item_value, str):
                return item_value
            raise ValueError('Invalid dict.')
        else:
            return numeric

    def parse_dict_item(item_string):
        if ':' in item_string:
            parts = item_string.split(':')
            if len(parts) != 2:
                raise ValueError('Invalid dict.')
            parts = [a.strip() for a in parts]

            if not uppercase:
                return ("%s" % parts[0], evaluate_dict_value(parts[1]))
            return (("%s" % parts[0]).upper(), evaluate_dict_value(parts[1]))

        else:
            raise ValueError('Invalid dict.')

    def parse_dict_items(self, dict_string):
        parsed = []
        items = dict_string.split(',')
        for item in items:
            parsed_item = parse_dict_item(item)
            parsed.append(parsed_item)
        return parsed

    if '{' in value and '}' in value:
        core_value = value[value.index('{') + 1:value.index('}')]
        if ',' in core_value:
            items = parse_dict_items(core_value)
        else:
            item = parse_dict_item(core_value)
            items = [item]

        return dict(items)

    else:
        raise ValueError('Invalid dict.')


def dict_switch_body(value, uppercase=False, default=None):

    default = default or {}
    default = default.copy()

    try:
        data = parse_dict_string(value, uppercase=uppercase)
    except ValueError as e:
        numeric = is_numeric(value)
        if numeric:
            new_default = {}
            for key, val in default.items():
                new_default[key] = numeric
            return new_default
        log.error(e)
    else:
        default.update(**data)
        return default


def dict_switch(name, default=None, uppercase=False, help=None, group=None):

    def wrapper(func):

        @cli.switch("--%s" % name, str, help=help, group=group)
        def wrapped(instance, value):
            data = dict_switch_body(value, uppercase=uppercase, default=default)
            return func(instance, data)

        return wrapped
    return wrapper


def method_switch(name, default=None, uppercase=True, help=None, group=None):

    def wrapper(func):

        @cli.switch("--%s" % name, str, help=help, group=group)
        def wrapped(instance, value):
            data = dict_switch_body(value, uppercase=uppercase, default=default)
            return func(instance, data)

        return wrapped
    return wrapper
