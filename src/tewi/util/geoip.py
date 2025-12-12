from functools import cache

from .log import get_logger, log_time

logger = get_logger()

# Try to import geoip module, set flag if not available
try:
    from geoip2fast import GeoIP2Fast

    geoip = GeoIP2Fast()
    _geoip_available = True
except ImportError:
    logger.warning(
        "GeoIP module (geoip2fast) not available, "
        "country detection for peers will not work, "
        "unless provided by torrent client itself"
    )
    geoip = None
    _geoip_available = False


@log_time
@cache
def get_country(address: str) -> str | None:
    if not _geoip_available:
        return None

    country_name = geoip.lookup(address).country_name
    return None if country_name == "<not found in database>" else country_name
