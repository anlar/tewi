# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2025  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from functools import cache
from typing import Any

from ..common import FileDTO, FilePriority
from .decorator import log_time
from .print import print_size


@log_time
def get_file_list(files: list[FileDTO]) -> list[dict[str, Any]]:
    """Convert file list to flattened tree structure with display formatting."""
    node = create_file_tree(files)

    items_list: list[dict[str, Any]] = []

    def flatten_tree(
            node: dict[str, Any], prefix: str = "", is_last: bool = True, depth: int = 0, current_path: str = ""
    ) -> None:
        """Recursively flatten tree structure into list with tree symbols."""
        items = [(k, v) for k, v in node.items() if k != '__is_file__']
        # Sort items by name (case-insensitive)
        items.sort(key=lambda x: x[0].lower())

        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1

            # Choose the appropriate tree characters
            if prefix == "":
                current_prefix = ""
                symbol = ""  # No prefix for first level files
            else:
                symbol = "├─ " if not is_last_item else "└─ "
                current_prefix = prefix

            display_name = f"{current_prefix}{symbol}{name}"

            # Build the path for this item
            item_path = f"{current_path}{name}" if current_path else name

            if subtree.get('__is_file__', False):
                f = subtree['file']
                completion = (f.completed / f.size) * 100
                items_list.append({
                    'is_file': True,
                    'display_name': display_name,
                    'id': f.id,
                    'size': print_size(f.size),
                    'done': f'{completion:.0f}%',
                    'priority': print_priority(f.priority),
                    'file_priority': f.priority,  # Store raw priority for styling
                    'depth': depth,  # Track tree depth
                    'folder_path': None  # Files don't have folder_path
                })
            else:
                items_list.append({
                    'is_file': False,
                    'display_name': display_name,
                    'id': None,
                    'size': None,
                    'done': None,
                    'priority': None,
                    'file_priority': None,
                    'depth': depth,  # Track tree depth
                    'folder_path': item_path  # Store folder path for child detection
                })

                extension = "│  " if not is_last_item else "  "
                new_prefix = current_prefix + extension
                # Pass folder path with trailing slash for next level
                next_path = f"{item_path}/"
                flatten_tree(subtree, new_prefix, is_last_item, depth + 1, next_path)

    flatten_tree(node)

    return items_list


@log_time
def create_file_tree(files: list[FileDTO]) -> dict[str, Any]:
    """Build hierarchical tree structure from flat list of files."""
    tree: dict[str, Any] = {}

    for file in files:
        parts = file.name.split('/')
        current = tree

        # Navigate/create the path in the tree
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}

            # If this is the last part (filename), mark it as a file
            if i == len(parts) - 1:
                current[part]['__is_file__'] = True
                current[part]['file'] = file

            current = current[part]

    return tree


@log_time
@cache
def print_priority(priority: FilePriority) -> str:
    """Convert file priority to Rich markup string with visual indicator."""
    match priority:
        case FilePriority.NOT_DOWNLOADING:
            return "[dim]-[/]"
        case FilePriority.LOW:
            return "[dim yellow]↓[/]"
        case FilePriority.MEDIUM:
            return '→'
        case FilePriority.HIGH:
            return '[bold red]↑[/]'
