from instattack.conf import settings


def get_env_file():
    filepath = settings.ROOT_DIR / '.env'
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
