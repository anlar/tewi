"""Torrent search provider implementations."""

from .yts import YTSProvider
from .torrentscsv import TorrentsCsvProvider
from .tpb import TPBProvider
from .nyaa import NyaaProvider
from .jackett import JackettProvider
from .prowlarr import ProwlarrProvider

__all__ = [
    "YTSProvider",
    "TorrentsCsvProvider",
    "TPBProvider",
    "NyaaProvider",
    "JackettProvider",
    "ProwlarrProvider",
]
