import re

from .log import log_time

# BitTorrent v1 info hash: 40-char hex (SHA-1) or 32-char Base32
_HASH_HEX_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_HASH_BASE32_RE = re.compile(r"^[A-Za-z2-7]{32}$")


@log_time
def is_torrent_link(text: str) -> bool:
    """Check if text appears to be a torrent link or magnet URI.

    Case-insensitive check for magnet:, http://, or https:// prefixes.
    """
    return text.strip().lower().startswith(("magnet:", "http://", "https://"))


@log_time
def is_torrent_hash(text: str) -> bool:
    """Check if text is a bare BitTorrent v1 info hash.

    Accepts a 40-character hex-encoded or 32-character Base32-encoded
    SHA-1 hash, as used in the `xt=urn:btih:` part of magnet URIs.
    """
    value = text.strip()
    return bool(_HASH_HEX_RE.match(value) or _HASH_BASE32_RE.match(value))
