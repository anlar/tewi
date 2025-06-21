from textual.message import Message


class AddTorrent(Message):

    def __init__(self, value: str, is_link: bool) -> None:
        super().__init__()
        self.value = value
        self.is_link = is_link


class TorrentLabelsUpdated(Message):

    def __init__(self, torrent_ids, value: str) -> None:
        super().__init__()
        self.torrent_ids = torrent_ids
        self.value = value


class SearchTorrent(Message):

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class SortOrderSelected(Message):

    def __init__(self, order: str, is_asc: bool) -> None:
        super().__init__()
        self.order = order
        self.is_asc = is_asc
