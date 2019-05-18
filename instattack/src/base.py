# -*- coding: utf-8 -*-
from dataclasses import dataclass

from .mixins import HandlerMixin, MethodHandlerMixin


class BaseHandler(object):

    def __init__(self, **kwargs):
        self.engage(**kwargs)


class Handler(BaseHandler, HandlerMixin):
    pass


class MethodHandler(BaseHandler, MethodHandlerMixin):
    pass


@dataclass
class TaskContext:

    def log_context(self, **kwargs):
        data = self.__dict__.copy()
        data['task'] = self.name
        data.update(**kwargs)
        return data
