"""Masking of secrets in text written to log or shown in UI."""

import re

# User info (user:password@) in URL
_URL_USERINFO_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s'\"]+@")

# Query parameters which names look like secrets: apikey, jackett_apikey,
# passkey, torrent_pass, authkey, token, ...
_SECRET_PARAM_RE = re.compile(
    r"(?i)([?&;][^=&\s#'\"]*(?:key|pass|token|auth|secret|sig)"
    r"[^=&\s#'\"]*=)[^&\s#'\"]+"
)

# Credentials of HTTP Authorization header (e.g. logged by client libraries)
_AUTH_HEADER_RE = re.compile(
    r"(?i)\b((?:basic|bearer|digest)\s+)[a-z0-9._~+/=-]{8,}"
)

MASK = "***"


def redact_secrets(text: str) -> str:
    """Mask passwords, API keys and passkeys in URLs and auth headers.

    Secrets embedded in URL path (e.g. /announce/PASSKEY) can't be
    recognized and are kept.
    """
    text = _URL_USERINFO_RE.sub(rf"\1{MASK}@", text)
    text = _SECRET_PARAM_RE.sub(rf"\1{MASK}", text)
    return _AUTH_HEADER_RE.sub(rf"\1{MASK}", text)
