import types
import functools
from instattack import logger
from instattack.logger import AsyncLogger, SyncLogger


class TestLogger(SyncLogger):
    adaptable = ('info', 'warning', )

    def format_message(self, data):
        return f"Formatted : {data}"

    def adapt(self, obj):

        class_copy = type('class_copy', self.__class__.__bases__, dict(self.__class__.__dict__))

        methods = [method_name for method_name in dir(obj)
            if callable(getattr(obj, method_name)) and method_name in self.adaptable]
        for method_name in methods:
            new_method = getattr(obj, method_name)
            # Produces a callable that behaves like draw2, but automatically passes p1 as the first argument.
            new_method = new_method.__get__(self)
            setattr(class_copy, method_name, new_method)
        return class_copy
        # self.info = types.FunctionType(func_code, new_info.func_globals, 'new_info')


class Addapted(object):

    def format_message(self, data):
        return f"Formatted : {data}"

    def info(self, message):
        print(f"Adapated Message {self.format_message(message)}")

    def warning(self, message):
        print(f"Adapated Message {self.format_message(message)}")


def test_info(instance, message):
    print('okay')


def test():

    log = logger.get_sync('Test Logger')
    log = TestLogger('Test Logger')
    adapted = log.adapt(Addapted)

    adapted.info('BLAH')

    log = logger.get_sync('Test Logger')
    log = TestLogger('Test Logger')

    log.info('Not Adapted')


async def main():
    test()


# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())
# loop.run_forever()

test()
