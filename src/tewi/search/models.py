from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..util.misc import RemoteData


@dataclass(frozen=True)
class Category:
    """Torrent category (Newznab standard, used by Jackett and Prowlarr)."""

    id: int
    name: str
    parent: Category | None = None

    @property
    def full_path(self) -> str:
        """Full hierarchical path like 'Books/EBook'."""
        if self.parent:
            return f"{self.parent.name}/{self.name}"
        return self.name

    @property
    def is_parent(self) -> bool:
        """Whether this is a parent category (ID ends in 000)."""
        return self.id % 1000 == 0


class StandardCategories:
    """Full list of categories.

    Parent categories are the ones users select: in search dialog and by
    name in search presets of config file. Every provider maps them to its
    own categories or filters results by them, so their IDs and names
    shouldn't change.

    Subcategories are only used for search results: providers map their
    categories to the most specific one, which is shown in results and
    matched by its parent when filtering, so the list can include every
    known subcategory.

    Based on:

    * https://github.com/Jackett/Jackett/wiki/Jackett-Categories
    * https://github.com/Prowlarr/Prowlarr/blob/develop/src/NzbDrone.Core/Indexers/NewznabStandardCategory.cs
    """

    # Parent categories
    CONSOLE = Category(1000, "Console")
    MOVIES = Category(2000, "Movies")
    AUDIO = Category(3000, "Audio")
    PC = Category(4000, "PC")
    TV = Category(5000, "TV")
    XXX = Category(6000, "XXX")
    BOOKS = Category(7000, "Books")
    OTHER = Category(8000, "Other")

    # Console subcategories
    CONSOLE_NDS = Category(1010, "NDS", CONSOLE)
    CONSOLE_PSP = Category(1020, "PSP", CONSOLE)
    CONSOLE_WII = Category(1030, "Wii", CONSOLE)
    CONSOLE_XBOX = Category(1040, "XBox", CONSOLE)
    CONSOLE_XBOX360 = Category(1050, "XBox 360", CONSOLE)
    CONSOLE_WIIWARE = Category(1060, "Wiiware", CONSOLE)
    CONSOLE_XBOX360DLC = Category(1070, "XBox 360 DLC", CONSOLE)
    CONSOLE_PS3 = Category(1080, "PS3", CONSOLE)
    CONSOLE_OTHER = Category(1090, "Other", CONSOLE)
    CONSOLE_3DS = Category(1110, "3DS", CONSOLE)
    CONSOLE_PSVITA = Category(1120, "PS Vita", CONSOLE)
    CONSOLE_WIIU = Category(1130, "WiiU", CONSOLE)
    CONSOLE_XBOXONE = Category(1140, "XBox One", CONSOLE)
    CONSOLE_PS4 = Category(1180, "PS4", CONSOLE)

    # Movies subcategories
    MOVIES_FOREIGN = Category(2010, "Foreign", MOVIES)
    MOVIES_OTHER = Category(2020, "Other", MOVIES)
    MOVIES_SD = Category(2030, "SD", MOVIES)
    MOVIES_HD = Category(2040, "HD", MOVIES)
    MOVIES_UHD = Category(2045, "UHD", MOVIES)
    MOVIES_BLURAY = Category(2050, "BluRay", MOVIES)
    MOVIES_3D = Category(2060, "3D", MOVIES)
    MOVIES_DVD = Category(2070, "DVD", MOVIES)
    MOVIES_WEBDL = Category(2080, "WEB-DL", MOVIES)
    MOVIES_X265 = Category(2090, "x265", MOVIES)

    # Audio subcategories
    AUDIO_MP3 = Category(3010, "MP3", AUDIO)
    AUDIO_VIDEO = Category(3020, "Video", AUDIO)
    AUDIO_AUDIOBOOK = Category(3030, "Audiobook", AUDIO)
    AUDIO_LOSSLESS = Category(3040, "Lossless", AUDIO)
    AUDIO_OTHER = Category(3050, "Other", AUDIO)
    AUDIO_FOREIGN = Category(3060, "Foreign", AUDIO)

    # PC subcategories
    PC_0DAY = Category(4010, "0day", PC)
    PC_ISO = Category(4020, "ISO", PC)
    PC_MAC = Category(4030, "Mac", PC)
    PC_MOBILE_OTHER = Category(4040, "Mobile-Other", PC)
    PC_GAMES = Category(4050, "Games", PC)
    PC_MOBILE_IOS = Category(4060, "Mobile-iOS", PC)
    PC_MOBILE_ANDROID = Category(4070, "Mobile-Android", PC)

    # TV subcategories
    TV_WEBDL = Category(5010, "WEB-DL", TV)
    TV_FOREIGN = Category(5020, "Foreign", TV)
    TV_SD = Category(5030, "SD", TV)
    TV_HD = Category(5040, "HD", TV)
    TV_UHD = Category(5045, "UHD", TV)
    TV_OTHER = Category(5050, "Other", TV)
    TV_SPORT = Category(5060, "Sport", TV)
    TV_ANIME = Category(5070, "Anime", TV)
    TV_DOCUMENTARY = Category(5080, "Documentary", TV)
    TV_X265 = Category(5090, "x265", TV)

    # XXX subcategories
    XXX_DVD = Category(6010, "DVD", XXX)
    XXX_WMV = Category(6020, "WMV", XXX)
    XXX_XVID = Category(6030, "XviD", XXX)
    XXX_X264 = Category(6040, "x264", XXX)
    XXX_UHD = Category(6045, "UHD", XXX)
    XXX_PACK = Category(6050, "Pack", XXX)
    XXX_IMAGESET = Category(6060, "ImageSet", XXX)
    XXX_OTHER = Category(6070, "Other", XXX)
    XXX_SD = Category(6080, "SD", XXX)
    XXX_WEBDL = Category(6090, "WEB-DL", XXX)

    # Books subcategories
    BOOKS_MAGS = Category(7010, "Mags", BOOKS)
    BOOKS_EBOOK = Category(7020, "EBook", BOOKS)
    BOOKS_COMICS = Category(7030, "Comics", BOOKS)
    BOOKS_TECHNICAL = Category(7040, "Technical", BOOKS)
    BOOKS_OTHER = Category(7050, "Other", BOOKS)
    BOOKS_FOREIGN = Category(7060, "Foreign", BOOKS)

    # Other subcategories
    OTHER_MISC = Category(8010, "Misc", OTHER)
    OTHER_HASHED = Category(8020, "Hashed", OTHER)

    @classmethod
    def get_by_id(cls, id: int) -> Category | None:
        """Get category by ID."""
        return next(
            (
                c
                for c in vars(cls).values()
                if isinstance(c, Category) and c.id == id
            ),
            None,
        )

    @classmethod
    def all_categories(cls) -> list[Category]:
        """Get all categories, sorted by ID."""
        categories = [c for c in vars(cls).values() if isinstance(c, Category)]
        return sorted(categories, key=lambda c: c.id)

    @classmethod
    def parent_categories(cls) -> list[Category]:
        """Get only parent categories."""
        return [c for c in cls.all_categories() if c.is_parent]


@dataclass(frozen=True)
class Indexer(RemoteData):
    """Search target, selectable in search dialog and search presets.

    Built-in providers have a single indexer with provider ID (e.g.
    "tpb"). Jackett and Prowlarr list their configured indexers, or a
    single one for all of them when not searched separately
    ("jackett:all", "prowlarr:all").
    """

    # Provider ID, or aggregator prefix with its indexer ID (e.g.
    # "jackett:1337x", "prowlarr:12"), used in search presets
    id: str
    # Shown in search dialog
    name: str
    # Plain text name of aggregator (e.g. "Jackett"), shown after name
    source: str | None = None


@dataclass(frozen=True)
class DetailsLink(RemoteData):
    """Link in search result details, opened in browser when clicked.

    Only HTTP(S) URLs are opened (see App.open_url).
    """

    url: str


@dataclass(frozen=True)
class DetailsSection(RemoteData):
    """Section of search result details.

    Text is shown literally, never parsed as markup. Section shows fields,
    items and text in this order, skipping empty ones.
    """

    title: str
    # Rows of label and value
    fields: tuple[tuple[str, str | DetailsLink], ...] = ()
    # List entries (e.g. files)
    items: tuple[str, ...] = ()
    # Paragraph, for long text (e.g. description)
    text: str | None = None


@dataclass(frozen=True)
class SearchPreset:
    """Named preset for search with specific indexers and categories."""

    name: str
    # None selects all indexers/categories
    indexers: tuple[str, ...] | None = None
    categories: tuple[str, ...] | None = None


@dataclass(frozen=True)
class SearchResult(RemoteData):
    """Data Transfer Object for web search results.

    Title is required. Info hash is lowercase 40-char hex (see
    `parse_info_hash`), or None if provider doesn't report it.
    """

    title: str
    info_hash: str | None
    magnet_link: str | None
    torrent_link: str | None

    provider: str
    provider_id: str
    provider_short: str
    # Plain text short tag of aggregator (e.g. "J"), shown after provider
    provider_source: str | None = None

    categories: tuple[Category, ...] = ()
    seeders: int | None = None
    leechers: int | None = None
    downloads: int | None = None  # Download/grabs count
    size: int | None = None  # bytes
    files_count: int | None = None
    upload_date: datetime | None = None  # Local time (see `local_time`)
    page_url: str | None = None  # Link to torrent page on provider site
    freeleech: bool = False

    # Provider-specific metadata
    extra: dict[str, object] = field(default_factory=dict)
