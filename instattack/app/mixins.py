# -*- coding: utf-8 -*-
import contextlib

from instattack.lib import logger


class LoggerMixin(object):

    def create_logger(self, subname, ignore_config=False, sync=False):
        if not sync:
            log = logger.get_async(self.__name__, subname=subname)
        else:
            log = logger.get_sync(self.__name__, subname=subname)

        if hasattr(self, '__logconfig__') and not ignore_config:
            log_level = self.config['log'][self.__logconfig__]
            log.setLevel(log_level.upper())

        return log

    @contextlib.asynccontextmanager
    @classmethod
    async def async_logger(cls, subname, ignore_config=False):
        try:
            log = logger.get_async(cls.__name__, subname=subname)
            yield log
        finally:
            await log.flush()
            await log.close()
