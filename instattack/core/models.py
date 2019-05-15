# -*- coding: utf-8 -*-
from dataclasses import dataclass


__all__ = ('TaskContext', )


@dataclass
class TaskContext:

    def log_context(self, **kwargs):
        data = self.__dict__.copy()
        data['task'] = self.name
        data.update(**kwargs)
        return data
