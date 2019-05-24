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


ROOT_DIR = DIR_STR(GET_ROOT())
USER_DIR = DIR_STR(GET_USER_ROOT())
APP_ROOT = DIR_STR(GET_APP_ROOT())
