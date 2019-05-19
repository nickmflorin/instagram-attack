# -*- coding: utf-8 -*-
from dataclasses import dataclass

from instattack.lib import Identifier


class ModelMixin(object):

    name = Identifier()

    @classmethod
    def count_all(cls):
        """
        Do not ask me why the count() method returns a CountQuery that does
        not have an easily accessible integer value.
        """
        return cls.all().count().__sizeof__()


class HandlerMixin(object):

    name = Identifier()

    def engage(self, lock=None, start_event=None, stop_event=None,
            user=None, queue=None):

        self._stopped = False
        self.lock = lock

        self.stop_event = stop_event
        self.start_event = start_event
        self.user = user


class BaseHandler(object):

    def __init__(self, **kwargs):
        self.engage(**kwargs)


class Handler(BaseHandler, HandlerMixin):

    @property
    def starting_message(self):
        return f"Starting {self.name}"


@dataclass
class TaskContext:

    def log_context(self, **kwargs):
        data = self.__dict__.copy()
        data['task'] = self.name
        data.update(**kwargs)
        return data
