import asyncio
from plumbum import local
from tortoise.transactions import in_transaction

from instattack import settings
from instattack.db import database_init

from instattack.lib import AppLogger, validate_method
from .proxies import Proxy

"""
Some useful code playing around with file permissions and plumbum.  We shouldn't
have permission issues so as long as these files are created inside the Python
app and not by the root user.

-----------------
Effective Group ID: os.getegid()
Real Group ID: os.geteuid()
Effective User ID:  os.getgid()

------
Changing File Modes and Permissions

os.chmod(filename, 0o644)

file.chmod(stat.S_IWRITE)
path.chmod(777)
newpath.chown(owner=os.geteuid(), group=os.getgid())
"""

"""
Some of these checks might not be necessary because we check the existence of
a user based on the presence of the username folder, so checking if that exists
after using it to determine if the user exists is redundant.  But it keeps the
control flow consistent and over cautious is never a bad thing.
"""


def get_data_dir():
    """
    TODO:
    ----
    Find a way to make this relative so we do not get stuck if we are running
    commands from nested portions of the app.
    """
    path = local.cwd / settings.USER_DIR
    if not path.exists():
        path.mkdir()
    return path


async def stream_proxies(method, limit=None):

    method = validate_method(method)
    async for proxy in Proxy.filter(method=method).all():
        yield proxy


async def find_proxy(proxy):
    saved = await Proxy.filter(
        host=proxy.host,
        port=proxy.port,
        method=proxy.method,
    ).first()
    return saved


async def update_or_create_proxy(proxy):
    saved = await find_proxy(proxy)
    if saved:
        differences = saved.compare(proxy, return_difference=True)
        if differences:
            saved.avg_resp_time = proxy.avg_resp_time
            saved.error_rate = proxy.error_rate
            await saved.save()
        return False, differences
    else:
        await proxy.save()
        return True, None


async def update_or_create_proxies(method, proxies):

    log = AppLogger('Updating/Creating Proxies')

    tasks = []
    async with in_transaction():
        for proxy in proxies:
            task = asyncio.create_task(update_or_create_proxy(proxy))
            tasks.append(task)

    results = await asyncio.gather(*tasks)

    num_created = len([res for res in results if res[0]])
    num_updated = len([res for res in results if res[1] and not res[1].none])

    log.info(f'Created {num_created} {method} Proxies')
    log.info(f'Updated {num_updated} {method} Proxies')
