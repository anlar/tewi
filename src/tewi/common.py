from typing import NamedTuple


class PageState(NamedTuple):
    current: int
    total: int


class SortOrder(NamedTuple):
    id: str
    name: str
    key_asc: str
    key_desc: str
    sort_func: None


sort_orders = [
        SortOrder('age', 'Age', 'a', 'A',
                  lambda t: t.added_date),
        SortOrder('name', 'Name', 'n', 'N',
                  lambda t: t.name.lower()),
        SortOrder('size', 'Size', 'z', 'Z',
                  lambda t: t.total_size),
        SortOrder('status', 'Status', 't', 'T',
                  lambda t: t.status),
        SortOrder('priority', 'Priority', 'i', 'I',
                  lambda t: t.priority),
        SortOrder('queue_order', 'Queue Order', 'o', 'O',
                  lambda t: t.queue_position),
        SortOrder('ratio', 'Ratio', 'r', 'R',
                  lambda t: t.ratio),
        SortOrder('progress', 'Progress', 'p', 'P',
                  lambda t: t.percent_done),
        SortOrder('activity', 'Activity', 'y', 'Y',
                  lambda t: t.activity_date),
        SortOrder('uploaded', 'Uploaded', 'u', 'U',
                  lambda t: t.uploaded_ever),
        SortOrder('peers', 'Peers', 'e', 'E',
                  lambda t: t.peers_connected),
        SortOrder('seeders', 'Seeders', 's', 'S',
                  lambda t: t.peers_sending_to_us),
        SortOrder('leechers', 'Leechers', 'l', 'L',
                  lambda t: t.peers_getting_from_us),
        ]
