# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline details of every provider never request network, as they are
generated in UI thread."""

from unittest.mock import patch

import pytest

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.manager import AVAILABLE_PROVIDERS
from src.tewi.search.models import SearchResult
from src.tewi.search.providers import (
    BitmagnetProvider,
    JackettProvider,
    ProwlarrProvider,
)


def create(provider_id: str) -> BaseSearchProvider:
    match provider_id:
        case "jackett":
            return JackettProvider("http://jackett", "key")
        case "prowlarr":
            return ProwlarrProvider("http://prowlarr", "key")
        case "bitmagnet":
            return BitmagnetProvider("http://bitmagnet")
    return AVAILABLE_PROVIDERS[provider_id]()


@pytest.mark.parametrize("provider_id", list(AVAILABLE_PROVIDERS))
def test_offline_details_dont_request_network(provider_id):
    provider = create(provider_id)
    # IDs used by providers to download details
    result = SearchResult(
        title="title",
        info_hash="a" * 40,
        magnet_link=None,
        torrent_link=None,
        provider=provider.name,
        provider_id=provider.id,
        provider_short=provider.short_name,
        extra={"torrent_id": "1", "media_id": "2"},
    )

    with (
        patch("src.tewi.search.base._urlopen") as get,
        patch("src.tewi.search.base._urlopen_post") as post,
    ):
        try:
            sections = provider.details_extended_offline(result)
        except Exception:
            # Only network requests are checked, not generic extra
            sections = []

    assert get.call_count == post.call_count == 0
    if provider.remote_details:
        assert sections is None
