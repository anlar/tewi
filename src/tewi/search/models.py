from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class Category:
    """Represents a Jackett category with ID, name, and hierarchy support."""

    def __init__(self, id: int, name: str, parent: Optional["Category"] = None):
        self.id = id
        self.name = name
        self.parent = parent

    @property
    def full_path(self) -> str:
        """Returns full hierarchical path like 'Console/XBox 360'."""
        if self.parent:
            return f"{self.parent.name}/{self.name}"
        return self.name

    @property
    def full_name(self) -> str:
        """Alias for full_path for backward compatibility."""
        return self.full_path

    @property
    def is_parent(self) -> bool:
        """Returns True if this is a parent category (ID ends in 000)."""
        return self.id % 1000 == 0

    def __repr__(self) -> str:
        return f"Category(id={self.id}, name='{self.name}')"


class StandardCategories:
    """Full list of categories.

    Parent categories shouldn't change - they are used as parameters
    for search providers (Prowlarr, Jackett).

    Sub-categories are only used to parse search results so they could
    contain maximum set of categories.

    List built from Jackett categories with addition of missing categories
    from Prowlarr.

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
    def get_by_id(cls, id: int) -> Optional[Category]:
        """Get category by ID."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Category) and attr.id == id:
                return attr
        return None

    @classmethod
    def all_categories(cls) -> list[Category]:
        """Get all categories."""
        categories = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Category):
                categories.append(attr)
        return sorted(categories, key=lambda c: c.id)

    @classmethod
    def parent_categories(cls) -> list[Category]:
        """Get only parent categories."""
        return [c for c in cls.all_categories() if c.is_parent]


@dataclass(frozen=True)
class Indexer:
    id: str
    name: str


@dataclass(frozen=True)
class SearchResult:
    """Data Transfer Object for web search results.

    Title is required.

    At least magnet_link or torrent_link required.

    Note: All size fields are in bytes.
    The fields dict contains provider-specific additional metadata.
    """

    # Required fields (torrent)
    title: str
    info_hash: str
    magnet_link: str
    torrent_link: str

    # Required fields (provider)
    provider: str
    provider_id: str

    # Optional fields - can be None if not available
    categories: list[Category] | None = None
    seeders: int | None = None
    leechers: int | None = None
    downloads: int | None = None  # Download/grabs count
    size: int | None = None  # bytes
    files_count: int | None = None
    upload_date: datetime | None = None
    page_url: str | None = None  # Link to torrent page on provider site
    freeleech: bool = False
    fields: dict[str, str] | None = None  # Provider-specific metadata
