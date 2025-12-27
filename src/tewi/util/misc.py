from .log import log_time


@log_time
def is_torrent_link(text: str) -> bool:
    """Check if text appears to be a torrent link or magnet URI.

    Case-insensitive check for magnet:, http://, or https:// prefixes.
    """
    return text.strip().lower().startswith(("magnet:", "http://", "https://"))
