from plumbum import LocalPath
import os
import site


def path_up_until(path, piece, as_string=True):
    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    if piece not in path.parts:
        raise ValueError(f'The path does not contain the piece {piece}.')

    index = path.parts.index(piece)
    parts = path.parts[:index + 1]
    full_path = os.path.join('/', *parts)
    if as_string:
        return full_path
    return LocalPath(full_path)


def is_log_file(path):
    pt = LocalPath(path)
    if 'logger' in pt.parts:
        log_file_path = path_up_until(path, 'logger')
        if path.startswith(log_file_path):
            return True
    return False


def is_site_package_file(path):
    site_packages = site.getsitepackages()
    for site_package in site_packages:
        if path.startswith(site_package):
            return True
    return False
