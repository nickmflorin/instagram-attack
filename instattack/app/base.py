# -*- coding: utf-8 -*-


class HandlerMixin(object):

    def create_logger(self, subname, ignore_config=False, sync=False):
        from instattack.lib import logger
        if not sync:
            log = logger.get_async(self.__name__, subname=subname)
        else:
            log = logger.get_sync(self.__name__, subname=subname)

        if not ignore_config:
            log_level = self.config['log'][self.__logconfig__]
            log.setLevel(log_level.upper())
        return log
