from geoip2fast import GeoIP2Fast
from functools import cache

geoip = GeoIP2Fast()


@cache
def get_country(address: str) -> str:
    return geoip.lookup(address).country_name
