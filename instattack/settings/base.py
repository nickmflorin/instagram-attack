from plumbum.path import LocalPath


APP_NAME = 'instattack'


def DIR_STR(path):
    return "%s/%s" % (path.dirname, path.name)


def GET_ROOT():
    parents = LocalPath(__file__).parents
    return [p for p in parents if p.name == APP_NAME][0].parent


def GET_USER_ROOT():
    return GET_ROOT() / "users"


def GET_APP_ROOT():
    return GET_ROOT() / APP_NAME


ROOT_PATH = GET_ROOT()
USER_PATH = GET_USER_ROOT()
APP_PATH = GET_APP_ROOT()

ROOT_DIR = DIR_STR(ROOT_PATH)
USER_DIR = DIR_STR(USER_PATH)
APP_DIR = DIR_STR(APP_PATH)
