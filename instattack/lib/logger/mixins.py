from instattack.config import settings


class SyncLoggerMixin(object):

    def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.SUCCESS.num):
            self._log(settings.LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    def start(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.START.num):
            self._log(settings.LoggingLevels.START.num, msg, args, **kwargs)

    def stop(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.STOP.num):
            self._log(settings.LoggingLevels.STOP.num, msg, args, **kwargs)

    def complete(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.COMPLETE.num):
            self._log(settings.LoggingLevels.COMPLETE.num, msg, args, **kwargs)

    def simple(self, msg, color=None, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({
            'color': color,
            'simple': True,
        })
        self._log(settings.LoggingLevels.INFO.num, msg, args, **kwargs)


class AsyncLoggerMixin(object):

    async def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.SUCCESS.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    async def start(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.START.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.START.num, msg, args, **kwargs)

    async def stop(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.STOP.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.STOP.num, msg, args, **kwargs)

    async def complete(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.COMPLETE.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.COMPLETE.num, msg, args, **kwargs)
