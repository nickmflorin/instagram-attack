from argparse import ArgumentTypeError
import collections
from copy import deepcopy
import json
import os
import yaml

from instattack import logger
from instattack.exceptions import ConfigurationError

from .utils import validate_config_filepath, validate_config_schema


log = logger.get_sync('Configuration')


class Configuration(collections.MutableMapping):
    """A dictionary that applies an arbitrary key-altering
       function before accessing the keys"""

    env_key = 'INSTATTACK_CONFIG'

    def __init__(self, data=None, top_level=False, path=None):

        self.store = dict()
        self.path = path
        if self.path:
            self.read()
        else:
            self.update(data or {}, top_level=top_level)

    def __getitem__(self, key):
        item = self.store[self.__keytransform__(key)]
        if isinstance(item, dict) and not isinstance(item, Configuration):
            return Configuration(item)
        return item

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, Configuration):
            value = Configuration(value)
        self.store[self.__keytransform__(key)] = value

    def __delitem__(self, key):
        del self.store[self.__keytransform__(key)]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __keytransform__(self, key):
        return key

    @classmethod
    def validate(cls, path):
        return validate_config_filepath(path)

    @classmethod
    def load(cls):
        data = os.environ[cls.env_key]
        data = json.loads(data)
        try:
            validate_config_schema(data)
        except ConfigurationError as e:
            log.critical('Configuration Not Valid After Loading from OS Environment')
            raise e
        return cls(data, top_level=True)

    def read(self):
        if not self.path:
            raise RuntimeError('Configuration must be provided a path in order to validate.')

        self.path = validate_config_filepath(self.path)

        with open(self.path, 'r') as ymlfile:
            try:
                data = yaml.load(ymlfile)
            except (yaml.YAMLLoadWarning, yaml.scanner.ScannerError) as e:
                raise ArgumentTypeError(str(e))

        validate_config_schema(data)

        # We do not want to recursively update present values since they should not
        # be present already, and if they are, we want to override the entire
        # structure.  Therefore we update the store directly, instead of using
        # the recursive update method.
        self.store.update(data)

    def recursively_update(self, newval):
        for k, v in newval.items():
            if k not in self:
                self[k] = v
            else:
                if isinstance(v, dict):
                    self[k].recursively_update(v)
                else:
                    self[k] = v

    def serialize(self):
        serialized = {}
        for k, v in self.store.items():
            if isinstance(v, Configuration):
                serialized[k] = v.serialize()
            else:
                serialized[k] = v
        return serialized

    def update(self, data, top_level=False):
        """
        Similar to regular dict update, but will only update nested dict values
        for single keys, not the entire structures.
        """
        if data:
            self.recursively_update(data)
        if top_level:
            self.set()

    def default(self, key, val):
        """
        Updates the current config object to have the default value (object/dict
        or singleton) for the provided key, and then returns the keyed object.

        If a dict is provided, only the values in the dict that are not already
        set will be updated/defaulted.

        NOTE:
        ----
        We have to manually call store on the main configuration object after
        this is performed.
        """
        self[key].update(val)
        return self[key]

    def set(self):
        try:
            validate_config_schema(self.store)
        except ConfigurationError as e:
            log.critical('Configuration Not Valid Before Storing in OS Environment')
            raise e

        os.environ[self.env_key] = json.dumps(self.serialize())

    def override(self, **kwargs):
        new_config = Configuration(deepcopy(self.store))
        new_config.update(**kwargs)

        try:
            validate_config_schema(new_config.store)
        except ConfigurationError as e:
            log.critical('Configuration Not Valid After Override')
            raise e
        return new_config
