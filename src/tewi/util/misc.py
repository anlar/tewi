import base64
import dataclasses
import re

from .log import log_time

# BitTorrent v1 info hash: 40-char hex (SHA-1) or 32-char Base32
_HASH_HEX_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_HASH_BASE32_RE = re.compile(r"^[A-Za-z2-7]{32}$")

# Control characters terminals may interpret (except tab and newline):
# ESC starts escape sequences, C1 range has 8-bit CSI and OSC
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# Text consisting of a single HTTP(S) URL and nothing else
_HTTP_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

# Profile and theme names. They are printed for shell completion, where
# bash "compgen -W" expands "$(...)", backticks and variables in them,
# and profile name is also a part of config file path.
_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

SAFE_NAME_RULE = (
    "letters, digits, '.', '_' and '-', starting with letter or digit"
)


@log_time
def is_torrent_link(text: str) -> bool:
    """Check if text appears to be a torrent link or magnet URI.

    Case-insensitive check for magnet:, http://, or https:// prefixes.
    """
    return text.strip().lower().startswith(("magnet:", "http://", "https://"))


@log_time
def is_http_url(text: str) -> bool:
    """Check if text is a single HTTP(S) URL and nothing else.

    Surrounding whitespace is ignored, but any other content (such as
    a description around the URL) makes the check fail.
    """
    return bool(_HTTP_URL_RE.match(text.strip())) if text else False


def strip_control_chars(value: str) -> str:
    """Remove control characters, which terminal could interpret.

    Text from torrents, peers, trackers and search providers could
    contain escape sequences (e.g. changing window title or clipboard),
    which would be passed to terminal as is.
    """
    return _CONTROL_CHARS_RE.sub("", value)


def _strip_control_chars_in(value):
    if isinstance(value, str):
        return strip_control_chars(value)
    if isinstance(value, list):
        return [_strip_control_chars_in(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_control_chars_in(v) for v in value)
    if isinstance(value, dict):
        return {k: _strip_control_chars_in(v) for k, v in value.items()}
    return value


def _strip_control_chars_in_fields(obj) -> None:
    """Strip control characters from text fields of (frozen) dataclass.

    Handles str fields and lists, tuples or dicts of them.
    """
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        clean = _strip_control_chars_in(value)
        if clean != value:
            object.__setattr__(obj, field.name, clean)


class RemoteData:
    """Base for dataclasses holding remote data (from torrent client or
    search provider): control characters are removed from text fields
    when object is created.

    Subclasses with own `__post_init__` must call `super().__post_init__()`.
    """

    def __post_init__(self) -> None:
        _strip_control_chars_in_fields(self)


@log_time
def is_safe_name(name: str) -> bool:
    """Check if name is valid for profile or theme (see SAFE_NAME_RULE)."""
    return bool(_SAFE_NAME_RE.fullmatch(name))


@log_time
def is_torrent_hash(text: str) -> bool:
    """Check if text is a bare BitTorrent v1 info hash.

    Accepts a 40-character hex-encoded or 32-character Base32-encoded
    SHA-1 hash, as used in the `xt=urn:btih:` part of magnet URIs.
    """
    value = text.strip()
    return bool(_HASH_HEX_RE.match(value) or _HASH_BASE32_RE.match(value))


def normalize_torrent_hash(text: str) -> str:
    """Convert BitTorrent v1 info hash to lowercase hex form.

    The same hash can be written in hex of any case or in Base32, so
    hashes have to be normalized before comparing them.

    Args:
        text: Info hash (40-char hex or 32-char Base32)

    Returns:
        Lowercase 40-char hex hash, or text unchanged if it isn't a hash
    """
    if not is_torrent_hash(text):
        return text
    value = text.strip()
    if len(value) == 32:
        return base64.b32decode(value.upper()).hex()
    return value.lower()


def parse_count(value: object) -> int | None:
    """Convert count from remote source to int.

    Remote data (e.g. JSON from search providers) may have counts as text
    or garbage, which can't be shown, sorted or compared as numbers.

    Args:
        value: Count as non-negative int or digit string

    Returns:
        Count, or None if value isn't a valid count
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    return None
