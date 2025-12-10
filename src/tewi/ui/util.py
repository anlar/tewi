"""UI utility functions."""


def subtitle_keys(*key_desc_pairs: tuple[str, str]) -> str:
    """Format key bindings for border subtitle display.

    Args:
        *key_desc_pairs: Variable number of (key, description) tuples

    Returns:
        Formatted string like "(A) Add / (O) Open / (X) Close"

    Example:
        >>> subtitle_keys(("Y", "Yes"), ("N", "No"))
        "(Y) Yes / (N) No"
        >>> subtitle_keys(("Enter", "Search"), ("ESC", "Close"))
        "(Enter) Search / (ESC) Close"
    """
    return " / ".join(f"({key}) {desc}" for key, desc in key_desc_pairs)
