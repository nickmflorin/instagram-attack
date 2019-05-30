from plumbum.path import LocalPath

from instattack import settings


def get_app_stack_at(stack, step=1):
    frames = [
        frame for frame in stack
        if frame.filename.startswith(settings.APP_DIR)
    ]
    return frames[step]


def relative_to_root(path):

    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    # This only happens for the test.py file...  We should remove this conditional
    # when we do not need that functionality anymore.
    if settings.APP_NAME in path.parts:
        ind = path.parts.index(settings.APP_NAME)
        parts = path.parts[ind:]
        path = LocalPath(*parts)

    return settings.DIR_STR(path)


def task_is_third_party(task):
    """
    Need to find a more sustainable way of doing this, this makes
    sure that we are not raising exceptions for external tasks.
    """
    directory = get_task_path(task)
    return not directory.startswith(settings.APP_DIR)


def get_coro_path(coro):
    return coro.cr_code.co_filename


def get_task_path(task):
    return get_coro_path(task._coro)
