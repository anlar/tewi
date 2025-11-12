from geoip2fast import GeoIP2Fast
from functools import cache

from .decorator import log_time

geoip = GeoIP2Fast()


@log_time
@cache
def get_country(address: str) -> str:
    return geoip.lookup(address).country_name
