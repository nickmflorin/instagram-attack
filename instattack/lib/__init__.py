from .yaspin import SyncYaspin


def yaspin(*args, **kwargs):
    return SyncYaspin(*args, **kwargs)
