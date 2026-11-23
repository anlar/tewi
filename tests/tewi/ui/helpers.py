"""Shared helpers for UI tests."""

from datetime import datetime, timedelta

from src.tewi.torrent.models import Torrent
from src.tewi.ui.panel.listview import TorrentListViewPanel


def make_torrent(name: str, status: str = "seeding") -> Torrent:
    """Torrent with given name, hash derived from name."""
    return Torrent(
        id=None,
        hash=f"hash-{name}",
        name=name,
        status=status,
        total_size=100,
        size_when_done=100,
        left_until_done=0,
        percent_done=1.0,
        eta=timedelta(0),
        rate_upload=0,
        rate_download=0,
        ratio=1.0,
        peers_connected=0,
        peers_getting_from_us=0,
        peers_sending_to_us=0,
        uploaded_ever=0,
        priority=None,
        added_date=datetime(2026, 1, 1),
        activity_date=datetime(2026, 1, 1),
        queue_position=None,
        download_dir="/data",
        category=None,
        labels=[],
    )


def make_list_panel(page_size: int = 100) -> TorrentListViewPanel:
    """Torrent list in oneline view mode, with all client capabilities."""
    return TorrentListViewPanel(
        id="torrent-list",
        page_size=page_size,
        view_mode="oneline",
        capability_set_priority=True,
        capability_label=True,
        capability_category=True,
    )
