import asyncio
from instattack import logger
from instattack.src import setup
from instattack.conf import Configuration
from instattack.src.proxies.models import Proxy


log = logger.get_sync('Test')


async def test():

    config = Configuration(path="conf.yml")
    new_config = config.mutate({'log': {'silent_shutdown': True}})
    import ipdb; ipdb.set_trace()


loop = asyncio.get_event_loop()
setup(loop)
loop.run_until_complete(test())
loop.run_forever()


