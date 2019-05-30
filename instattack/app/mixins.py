# -*- coding: utf-8 -*-
from instattack.lib import logger


class LoggerMixin(object):

    def create_logger(self, subname, ignore_config=False, sync=False):
        if not sync:
            log = logger.get_async(self.__name__, subname=subname)
        else:
            log = logger.get_sync(self.__name__, subname=subname)
        return log
