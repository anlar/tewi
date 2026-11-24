"""Clipboard utilities for system clipboard access.

System clipboard is accessed with pyperclip, which runs helper programs
(xclip, wl-copy, pbcopy, etc.): calls may block, so they should run in
background threads.
"""

import os

from .log import get_logger, log_time

logger = get_logger()

# Environment variables set by SSH server in remote sessions
_SSH_ENV_VARS = ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")

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


def is_remote_session() -> bool:
    """Check if application runs in SSH session.

    System clipboard of remote machine is not the one user works with,
    and accessing it over forwarded X11 display may hang SSH session on
    logout (xclip keeps running in background to serve copied text).
    """
    return any(os.environ.get(v) for v in _SSH_ENV_VARS)


def is_available() -> bool:
    """Check if system clipboard can be used."""
    return _pyperclip_available and not is_remote_session()


@log_time
def paste() -> str | None:
    """
    Get text content from system clipboard.

    Returns:
        str | None: The clipboard text content, or None if clipboard is empty
                    or unavailable.
    """
    if not is_available():
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
    if not is_available():
        return False

    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        logger.warning(f"Failed to access clipboard: {e}")
        return False
