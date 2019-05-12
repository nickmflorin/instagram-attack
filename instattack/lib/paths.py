from plumbum.path import LocalPath

from instattack import settings


def dir_str(path):
    return "%s/%s" % (path.dirname, path.name)


def get_root():
    parents = LocalPath(__file__).parents
    return [p for p in parents if p.name == settings.APP_NAME][0].parent


def relative_to_root(path):
    """
    Returns a string representation of the path localized to the repository
    for easier and less hairy filepaths while logging.
    """
    if not isinstance(path, LocalPath):
        path = LocalPath(path)
    app_index = path.parts.index(settings.APP_NAME)
    return dir_str(LocalPath(*path.parts[app_index - 1:]))


def get_env_file():

    root = get_root()
    filepath = root / '.env'

    if not filepath.exists() or not filepath.is_file():
        filepath.touch()
    return filepath


def write_env_file(env_vars):

    file = get_env_file()
    lines = []
    for key, val in env_vars.items():
        lines.append(f"{key}={val}\n")
    file.write(''.join(lines))


def read_env_file():
    env_vars = {}

    def format_part(part):
        part = part.strip()
        part = part.replace("\'", '')
        part = part.replace('\"', '')
        return part

    file = get_env_file()
    data = file.read()

    lines = [line.strip() for line in data.split('\n')]
    for i, line in enumerate(lines):

        if '=' not in line or len(line.split('=')) != 2:
            continue
        else:
            parts = line.split('=')
            env_vars[format_part(parts[0])] = format_part(parts[1])
    return env_vars
