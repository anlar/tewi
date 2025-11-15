from geoip2fast import GeoIP2Fast
from functools import cache

from .decorator import log_time

geoip = GeoIP2Fast()


@log_time
@cache
def get_country(address: str) -> str | None:
    country_name = geoip.lookup(address).country_name
    return None if country_name == "<not found in database>" else country_name
