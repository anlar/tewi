"""Torrent search provider implementations."""

from .bitmagnet import BitmagnetProvider
from .bitsearch import BitsearchProvider
from .jackett import JackettProvider
from .nyaa import NyaaProvider
from .prowlarr import ProwlarrProvider
from .torrentscsv import TorrentsCsvProvider
from .tpb import TPBProvider
from .yts import YTSProvider

__all__ = [
    "BitmagnetProvider",
    "BitsearchProvider",
    "YTSProvider",
    "TorrentsCsvProvider",
    "TPBProvider",
    "NyaaProvider",
    "JackettProvider",
    "ProwlarrProvider",
]
