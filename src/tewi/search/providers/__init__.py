"""Torrent search provider implementations."""

from .bitmagnet import BitmagnetProvider
from .jackett import JackettProvider
from .nyaa import NyaaProvider
from .prowlarr import ProwlarrProvider
from .torrentscsv import TorrentsCsvProvider
from .torrentz2 import Torrentz2Provider
from .tpb import TPBProvider
from .yts import YTSProvider

__all__ = [
    "BitmagnetProvider",
    "YTSProvider",
    "TorrentsCsvProvider",
    "Torrentz2Provider",
    "TPBProvider",
    "NyaaProvider",
    "JackettProvider",
    "ProwlarrProvider",
]
