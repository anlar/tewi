# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Torrent search provider implementations."""

from .bitmagnet import BitmagnetProvider
from .bitsearch import BitsearchProvider
from .jackett import JackettProvider
from .knaben import KnabenProvider
from .limetorrents import LimeTorrentsProvider
from .nekobt import NekoBtProvider
from .nyaa import NyaaProvider
from .prowlarr import ProwlarrProvider
from .therarbg import TheRarbgProvider
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
    "KnabenProvider",
    "LimeTorrentsProvider",
    "NekoBtProvider",
    "ProwlarrProvider",
    "TheRarbgProvider",
]
