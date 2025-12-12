"""Clipboard utilities for getting content from system clipboard."""

from .log import get_logger, log_time

logger = get_logger()

# Try to import pyperclip, set flag if not available
try:
    import pyperclip

    _pyperclip_available = True
except ImportError:
    logger.warning(
        "pyperclip library not available, "
        "clipboard paste functionality will not work"
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
