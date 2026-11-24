"""Clipboard utilities for system clipboard access."""

from .log import get_logger, log_time

logger = get_logger()

# Try to import pyperclip, set flag if not available
try:
    import pyperclip

    _pyperclip_available = True
except ImportError:
    logger.warning(
        "pyperclip library not available, "
        "system clipboard functionality will not work"
    )
    pyperclip = None
    _pyperclip_available = False


@log_time
def paste() -> str | None:
    """
    Get text content from system clipboard.

    Returns:
        str | None: The clipboard text content, or None if clipboard is empty
                    or unavailable.
    """
    if not _pyperclip_available:
        return None

    try:
        text = pyperclip.paste()
        return text if text else None
    except Exception as e:
        logger.warning(f"Failed to access clipboard: {e}")
        return None


@log_time
def copy(text: str) -> bool:
    """
    Put text content to system clipboard.

    Args:
        text: Text to put to clipboard.

    Returns:
        bool: True if text was copied, False if clipboard is unavailable.
    """
    if not _pyperclip_available:
        return False

    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        logger.warning(f"Failed to access clipboard: {e}")
        return False
