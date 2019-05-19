from argparse import ArgumentTypeError
from copy import deepcopy
import json
import os
import yaml

from .utils import validate_config_filepath


class Configuration(dict):

    env_key = 'INSTATTACK_CONFIG'

    def __init__(self, path=None, data=None):
        self.path = path

        data = data or {}
        if data:
            data = self.recursively_wrap(data)
        super(Configuration, self).__init__(data)

    def recursively_wrap(self, data):
        created = {}
        for key, val in data.items():
            if isinstance(val, dict):
                created[key] = Configuration(self.path, data=val)
            else:
                created[key] = val
        return created

    def _validate(self):
        """
        Validates if the default configuration file or the specified config
        file is both present and valid, and then validates whether or not the
        schema is correct.
        """
        if not self.path:
            raise RuntimeError('Configuration must be provided a path in order to validate.')
        self.path = validate_config_filepath(self.path)

    def read(self):
        with open(self.path, 'r') as ymlfile:
            try:
                data = yaml.load(ymlfile)
            except (yaml.YAMLLoadWarning, yaml.scanner.ScannerError) as e:
                raise ArgumentTypeError(str(e))
            else:
                data = self.recursively_wrap(data)
                self.update(**data)

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
