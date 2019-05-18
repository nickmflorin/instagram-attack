import asyncio
from instattack import logger


log = logger.get_sync('my-sync-logger')
alogger = logger.get_async('my-logger')


def test():
    pass
    # logger.debug("SYNC")
    # logger.info("SYNC")
    log.success("START SYNC")
    # logger.warning("SYNC")
    # logger.error("SYNC")
    # logger.critical("SYNC")


async def main():

    # alogger.debug("ASYNC")
    # alogger.info("ASYNC")
    alogger.success('START ASYNC')

    # alogger.warning("ASYNC")
    # alogger.error("ASYNC")
    # alogger.critical("ASYNC")

    await alogger.shutdown()


test()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
