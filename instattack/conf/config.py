from argparse import ArgumentTypeError
from copy import deepcopy
import json
import os
import yaml

from .utils import validate_config_filepath


class Configuration(dict):

    env_key = 'INSTATTACK_CONFIG'

    def __init__(self, path=None, data=None):
        super(Configuration, self).__init__({})

        self.path = path
        if self.path:
            self.read()

        if data:
            self.establish(data)
        self.store()

    def read(self):
        self._validate()
        with open(self.path, 'r') as ymlfile:
            try:
                data = yaml.load(ymlfile)
            except (yaml.YAMLLoadWarning, yaml.scanner.ScannerError) as e:
                raise ArgumentTypeError(str(e))
        self.update(data)

    def establish(self, data):
        """
        Similiar to regular dict update, in that nested dicts update for the
        entire structure, but all dict structures are sub-nested as instances
        of Configuration.
        """
        for key, val in data.items():
            if isinstance(val, dict):
                # Will recursively update the nested dict objects in the __init__
                # method.
                self[key] = Configuration(data=val)
            else:
                self[key] = val

    def update(self, data):
        """
        Similar to regular dict update, but will only update nested dict values
        for single keys, not the entire structures.
        """
        def mutate_in_place(original, obj):
            for key, val in obj.items():
                if isinstance(val, dict):
                    if key in original:
                        mutate_in_place(original[key], val)
                    else:
                        original[key] = val
                else:
                    original[key] = val

        mutate_in_place(self, data)
        self.store()

    def _validate(self):
        """
        Validates if the default configuration file or the specified config
        file is both present and valid, and then validates whether or not the
        schema is correct.
        """
        if not self.path:
            raise RuntimeError('Configuration must be provided a path in order to validate.')
        self.path = validate_config_filepath(self.path)

    def store(self):
        os.environ[self.env_key] = json.dumps(self)

    @classmethod
    def load(cls):
        data = os.environ[cls.env_key]
        data = json.loads(data)
        return cls(data=data)

    @classmethod
    def validate(cls, path):
        config = Configuration(path)
        config._validate()
        config.read()
        return config

    def override(self, **kwargs):
        new_config = Configuration(self.path, data=deepcopy(self.data))
        return new_config
