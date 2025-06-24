def is_torrent_link(text: str) -> bool:
    """Check if text appears to be a torrent link or magnet URI."""
    return text.strip().startswith(('magnet:', 'http://', 'https://'))
