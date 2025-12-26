# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each change should be in one line, as GitHub markdown in release section can't
handle multi-line list body as single line.

## [Unreleased]

### Added

### Changed

- Resize table columns in torrent details panels for each torrent [#160](https://github.com/anlar/tewi/issues/160)
- Improve torrent/magnet link detection in Prowlarr search results

### Removed

## [2.2.0] - 2025-12-25 - Inaba Trace

### Added

- Add `--log-level` CLI and config option with 5 log levels (debug, info, warning, error, critical) [#152](https://github.com/anlar/tewi/issues/152)
- Add Bitmagnet torrent search provider with GraphQL API integration [#153](https://github.com/anlar/tewi/issues/153)
- Open files from torrent details with hotkey `Enter` [#156](https://github.com/anlar/tewi/issues/156)
- Add `--jackett-multi` and `--prowlarr-multi` CLI and config options to control indexer loading mode: when disabled (default), shows single provider entry in search dialog and searches all indexers; when enabled, loads all indexers individually for granular selection

### Changed

- Search providers now respect configuration order: providers listed first in config take priority when deduplicating results and appear first in search dialog [#154](https://github.com/anlar/tewi/issues/154)
- Default search provider order set to: tpb, yts, nyaa, torrentscsv, jackett, prowlarr, bitmagnet, torrentz2 [#154](https://github.com/anlar/tewi/issues/154)
- By default enable only built-in search providers
- Use theme colors for file priority icons in torrent files tab
- YTS provider: Strip query parameters from page URLs for cleaner links
- TPB provider: fix parsing error when `num_files` field is missing from API response

### Removed

- Remove `--logs` CLI and config option (replaced by `--log-level`) [#152](https://github.com/anlar/tewi/issues/152)

## [2.1.0] - 2025-12-15 - Rabbit Tiger

### Added

- Add Prowlarr torrent search provider [#133](https://github.com/anlar/tewi/issues/133)
- Display download count in search results [#137](https://github.com/anlar/tewi/issues/137)
- Display freeleech flag in torrent search results [#136](https://github.com/anlar/tewi/issues/136)
- Add `--path` CLI and config option to customize RPC path for Transmission and base JSON path for Deluge [#148](https://github.com/anlar/tewi/issues/148)
- Web search now remembers last selected indexers and categories ('w' hotkey for clean search, 'W' - for using last state)

### Changed

- Use `platformdirs` library to get location for config and logs directories [#140](https://github.com/anlar/tewi/issues/140)
- Log file moved to platform-specific directory [#140](https://github.com/anlar/tewi/issues/140)
- Optimize Jackett search (use 'all' endpoint or run indexers in parallel)
- Use ruff as linter (reformatted whole code base) [#135](https://github.com/anlar/tewi/issues/135)
- GeoIP module gracefully handles missing geoip2fast dependency
- clipboard module gracefully handles missing pyperclip dependency
- Refactor torrents clients: use torrent hash as ID in Transmission
- Use non-existent category during indexers loading from Jackett (speed up loading)
- Refactored code to split into torrent, search, ui modules

## [2.0.0] - 2025-12-07 - White Rabbit of Good Fortune

### Added

- Support for Deluge torrent client (via Web API) [#110](https://github.com/anlar/tewi/issues/110)
- Configuration profiles support (`--profile` option to load profile configs, `--profiles` to list available profiles) [#108](https://github.com/anlar/tewi/issues/108)
- Add Jackett torrent search provider [#118](https://github.com/anlar/tewi/issues/118)
- Configuration options `jackett_url` and `jackett_api_key` in [search] section
- Support for HTTP/HTTPS torrent file URLs in search results
- New `torrent_link` field in `SearchResultDTO` for torrent file URLs
- Automatic download and conversion of torrent files from URLs in Deluge client
- Display category and labels in torrent card
- Badge display options: `--badge-max-count` and `--badge-max-length` to control badge display in torrent cards
- Indexer selection in web search dialog - select which search providers/indexers to use for each search
- Category filtering in web search - search providers now support category filter in search requests
- Cache Jackett search indexers for 10 minutes [#131](https://github.com/anlar/tewi/issues/131)
- Option to specify enabled search providers: `--search-providers`, config `[search].providers` [#132](https://github.com/anlar/tewi/issues/132)
- Command to list avaialable search providers: `--list-search-providers` [#132](https://github.com/anlar/tewi/issues/132)

### Changed

- Search providers now send User-Agent headers to imitate popular browsers and prevent blocking
- Fix position sorting with empty queue numbers
- Configuration directory moved from `~/.config/` to `~/.config/tewi/`
- Remember last search query in search dialog
- Use Jackett torrent categories
- Make torrent search parameters selection move to the next line after toggle
- Refactored search providers: use only full name (removed short name)
- Escape markup characters in torrent names in web search results table

## [1.2.1] - 2025-11-30 - Sharing Krolik

### Changed

- Fix bug when adding new torrent from UI

## [1.2.0] - 2025-11-28 - Sharing Krolik

### Added

- Filter torrents by status with 'f' hotkey (all, active, downloading, seeding, paused, finished) [#102](https://github.com/anlar/tewi/issues/102)
- Toggle file download status in torrent details with 'space' key (files not downloading are dimmed)
- Change file download priority in torrent details with 'L', 'M', 'H' keys
- Action to open web link in torrent search results ('o' hotkey)
- Automatically refresh torrent details screen [#101](https://github.com/anlar/tewi/issues/101)
- Edit torrent name and location [#103](https://github.com/anlar/tewi/issues/103)
- Display search hits in status panel [#104](https://github.com/anlar/tewi/issues/104)
- Display qBittorrent-specific statistics (waste, connected peers, cache, performance) [#106](https://github.com/anlar/tewi/issues/106)
- Set torrent category with 'C' hotkey (qBittorrent only) [#105](https://github.com/anlar/tewi/issues/105)

### Changed

- Changed navigation hotkeys in torrent details to 'ofpt1234', allowed navigation in tables
- Display '-' instead of 'N/A' for missing tracker fields
- Start tracker tier number from 0 instead of 1
- Fix column resize in torrent search results table [#107](https://github.com/anlar/tewi/issues/107)

## [1.1.0] - 2025-11-20 - Moon Rabbit

### Added

- Web search for torrents on public trackers (YTS, TPB, Torrents-CSV, Nyaa)
- Start web search with query via `-s/--search` CLI option
- Torrent details view in search results ('i' hotkey)
- Change torrent bandwidth priority with 'p' hotkey (cycles through high/low/normal, Transmission only)
- Configuration file support with INI format stored in XDG_CONFIG_HOME or ~/.config [#98](https://github.com/anlar/tewi/issues/98)
- Display download and upload state (interested/choked) for peers
- Display tracker timing information in trackers table (last/next announce and scrape times, Transmission only)
- Set terminal title [#95](https://github.com/anlar/tewi/issues/95)

### Changed

- Display "-" instead of `"<not found in database>"` for peers with unrecognized IP addresses
- Load peer country from qBittorrent details
- Unified naming scheme for peer connection types
- Fix wrong order of upload and download speed columns in peers
- Use short country names for qbittorrent peers
- Merge priority and select columns in files (shorten rows)
- Change Progress column to Done in files (shorten rows)
- Sort files alphabetically by name in torrent details
- Shorten column names in trackers table
- Change hotkey for torrent status toggle from 'p' to 'Space'
- Create capabilities system to hide actions unsupported by client

## [1.0.0] - 2025-11-14 - Silver Whiskers

### Added

- Support for qBittorrent client
- CLI option to add torrent from file path or magnet link (`-a/--add-torrent`)
- Add Status, Message, and Peers columns to trackers table in torrent details
- Add Port, Connection Type, and Direction columns to peers table in torrent details
- Display colorized queue position and priority indicators in torrent list (shows #N prefix and ⬆/⬇ for high/low priority)
- Hidden `--test-mode N` option for performance testing (generates ~N test torrents)
- Display torrent status in color in card view mode

### Changed

- Refactoring: replaced custom list widget with native list view
- Reorder tracker columns: Tier, Host, Status, Peers, Seeders, Leechers, Downloads, Message
- Use speed formatter for alternative speed limits display (shows proper units: B, KB, MB, GB)
- Display "-" instead of "0 B/s" for zero speeds in peers
- Fix state panel artifact when alt speed is disabled
- Optimize session statistics calculation with single-pass algorithm
- Improved item highlight CSS code
- Add current timestamp to log file
- Set default number of torrents on page to 30
- Added left/right navigation with cursor keys
- Group keys in help dialog

### Removed

- Ability to mark torrents and perform group actions

## [0.9.0] - 2025-07-01 - Rabbit Warren

### Added

- Ability to mark torrents and perform group actions [#52](https://github.com/anlar/tewi/issues/52)

### Changed

- Move version variable to separate Python module
- Group actions in help dialog [#39](https://github.com/anlar/tewi/issues/39)
- Fix error when selected torrent was deleted in background [#82](https://github.com/anlar/tewi/issues/82)
- Display error message when failed to connect to Transmission [#83](https://github.com/anlar/tewi/issues/83)

## [0.8.1] - 2025-06-11 - Lunar Grove B

### Changed

- Fixed page indicator for Textual v2+ (disabled markup)

## [0.8.0] - 2025-06-09 - Lunar Grove

### Added

- Display file tree in torrent details

### Changed

- Support for Textual v2+ (disable label markup by default) [#71](https://github.com/anlar/tewi/issues/71)
- Expand file panel in torrent details
- Fix displaying hotkeys in dialogs in Textual v2+
- Cleanup and shorten statistics in torrent cards

## [0.7.0] - 2025-06-04 - Red Eyed Rabbit

### Added

- Search torrent by name [#25](https://github.com/anlar/tewi/issues/25)
- Display ago dates in torrent details
- Show Transmission server preferences [#43](https://github.com/anlar/tewi/issues/43)

### Changed

- Fix issue when delete last torrent in the list (it re-appears when scroll down)
- Multi-column layout for torrent details screen [#57](https://github.com/anlar/tewi/issues/57)
- Display "-" instead of "0" in speed indicators
- Make speed indicators bold when speed value is greater than zero
- Make torrent stats labels responsive to auto-resize [#72](https://github.com/anlar/tewi/issues/72)

## [0.6.1] - 2025-02-27 - Pet Rabbit B

### Changed

- Fix torrent add dialog crash when no clipboard manager installed [#56](https://github.com/anlar/tewi/issues/56)
- Limit max `textual` dependency version to v1.0.0

## [0.6.0] - 2025-01-21 - Pet Rabbit

### Added

- Actions to start/stop all torrents [#53](https://github.com/anlar/tewi/issues/53)
- Add home/end shortcuts to torrents list [#54](https://github.com/anlar/tewi/issues/54)

### Changed

- Fix error on start up when ReactiveLabel may not be initialized with value [#51](https://github.com/anlar/tewi/issues/51)
- Change style to exclude accent colors (use primary for selected item and secondary for panels)
- Fix scroll to the end of items list after re-draw [#50](https://github.com/anlar/tewi/issues/50)
- Fix screenshot action name in help window

## [0.5.0] - 2024-11-14 - Rabbit Orb

### Added

- Add verifying status to state panel statistics [#37](https://github.com/anlar/tewi/issues/37)
- Add action to save screenshot [#42](https://github.com/anlar/tewi/issues/42)
- Display free disk space in torrent add dialog [#40](https://github.com/anlar/tewi/issues/40)
- Add torrent from URL [#41](https://github.com/anlar/tewi/issues/41)
- Add more torrent list sort orders [#38](https://github.com/anlar/tewi/issues/38)
- Add torrent pieces info to torrent details
- Add torrent from local file [#45](https://github.com/anlar/tewi/issues/45)
- Show number of peers in torrent item [#47](https://github.com/anlar/tewi/issues/47)
- Add action to update torrent labels (displayed in torrent details) [#48](https://github.com/anlar/tewi/issues/48)
- Show ETA for downloading torrents

### Changed

- Hide statuses with zero torrents from state panel [#36](https://github.com/anlar/tewi/issues/36)
- More verbose torrent details: privacy, comment, creator, error
- Show Yes/No for selected files in torrent details
- Fix download percentage display in torrent item
- More compact view for peer details in torrent item card
- Store application version in single place [#44](https://github.com/anlar/tewi/issues/44)
- Dependencies: specify minimal version for all dependencies

## [0.4.1] - 2024-10-27 - Chasing Two Rabbits

### Changed

- Remove version.py to fix broken PyPI package

## [0.4.0] - 2024-10-27 - Chasing Two Rabbits

### Added

- Pagination for torrents list
- Display torrent uploaded size in torrent card and details
- Display downloaded, ratio and error fields in details
- Display total size of all torrents in state panel
- Build: setup Github dependabot
- Build: load Tewi version from single place

### Changed

- Split torrent card stats line into columns
- Use hotkeys to select sort order
- Fix help dialog auto-resize
- Dependencies: update textual from 0.83.0 to 0.85.0

## [0.3.0] - 2024-10-23 - White Rabbit

### Added

- Oneline view mode for torrents
- Display peer country in torrent details
- Show torrent size/progress/ratio in compact and oneline view modes
- Add torrent by magnet link
- Load magnet link from clipboard when adding torrent
- Torrents sort order
- CLI option to set refresh interval (`--refresh-interval`)
- CLI option to limit number of displayed torrents (`--limit-torrents`)
- CLI option to enable logfile (`--logs`)

### Changed

- Performance: optimize UI rendering by loading all torrent widgets together
- Performance: load Transmission data in separate thread
- Performance: add cache for all Util methods
- Fix tracker tier numbering (should start with Tier 1, not 0)
- Show statistics key changed to `S`
- Use cache for Util class

## [0.2.0] - 2024-10-17 - Runaway Rabbit

### Added

- View torrent details (overview, files, peers, trackers)
- View Transmission session statistics dialog
- Compact mode for torrent list
- Toast notifications for torrent actions
- Action to reannounce torrent
- Action to toggle dark/light interface modes
- CLI options to set username and password for daemon connection (`--username`, `--password`)
- Application title

### Changed

- Rewrite widgets tree structure (code cleanup/optimization)
- Display only keys for current screen in help dialog
- Use <X> key to close dialog (instead of <Q>)

## [0.1.0] - 2024-10-11 - Rabbit Sign

### Added

- Initial application implementation
