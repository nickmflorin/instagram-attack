from .scrapers import USProxyOrg, GatherProxyOrg


def scrape_proxies(limit=None):
    """
    [x] TODO:
    --------
    Adjust limit based on whether or not previous scrapers return a certain
    number of proxies - possibly make limit so that it refers to the limit of
    new proxies added from scrape.
    """
    scrapers = [GatherProxyOrg, USProxyOrg]
    scraped = []

    for scraper in scrapers:
        scrape = scraper(limit=limit)
        proxies = scrape()
        scraped.extend(proxies)

    return proxies
