from argparse import ArgumentTypeError
from copy import deepcopy
import yaml

from .utils import validate_config_filepath


class Configuration(dict):
    method_dir = {
        'GET': 'token',
        'POST': 'login',
    }

    def __init__(self, path, data=None):
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

    def for_method(self, method):
        return self[self.method_dir[method]]

    def validate(self):
        """
        Validates if the default configuration file or the specified config
        file is both present and valid, and then validates whether or not the
        schema is correct.
        """
        self.path = validate_config_filepath(self.path)
        with open(self.path, 'r') as ymlfile:
            try:
                data = yaml.load(ymlfile)
            except (yaml.YAMLLoadWarning, yaml.scanner.ScannerError) as e:
                raise ArgumentTypeError(str(e))
            else:
                data = self.recursively_wrap(data)
                self.update(**data)

    def override(self, **kwargs):
        new_config = Configuration(self.path, data=deepcopy(self.data))
        return new_config
