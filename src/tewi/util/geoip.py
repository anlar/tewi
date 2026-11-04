import os
from functools import lru_cache

from .log import get_logger, log_time

logger = get_logger()

GEOIP_CACHE_SIZE = 5000

# Try to import geoip module, set flag if not available
try:
    import geoip2fast
    from geoip2fast import GeoIP2Fast

    # Database bundled with library is passed by absolute path: by default
    # GeoIP2Fast looks for it in current directory first and loads it with
    # pickle, which would run code from any file with that name there
    _DATA_FILE = os.path.join(
        os.path.dirname(os.path.abspath(geoip2fast.__file__)),
        "geoip2fast.dat.gz",
    )
    geoip = GeoIP2Fast(geoip2fast_data_file=_DATA_FILE)
except ImportError:
    logger.warning(
        "GeoIP module (geoip2fast) not available, "
        "country detection for peers will not work, "
        "unless provided by torrent client itself"
    )
    geoip = None
except Exception as e:
    logger.warning(
        f"GeoIP database can't be loaded, country detection for peers "
        f"will not work, unless provided by torrent client itself: {e}"
    )
    geoip = None


@log_time
@lru_cache(maxsize=GEOIP_CACHE_SIZE)
def get_country(address: str) -> str | None:
    if geoip is None:
        return None

    country_name = geoip.lookup(address).country_name
    return None if country_name == "<not found in database>" else country_name
