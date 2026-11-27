# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each change should be in one line, as GitHub markdown in release section can't
handle multi-line list body as single line.

## [Unreleased]

### Added

- Add Bitsearch search provider (`bitsearch`), enabled by default
- Add Knaben search provider (`knaben`), meta-indexer of public trackers, enabled by default
- Add TheRARBG search provider (`therarbg`), enabled by default
- Add LimeTorrents search provider (`limetorrents`), enabled by default
- Add nekoBT anime search provider (`nekobt`), enabled by default
- Add maximum search time to web search status while searching
- Add marking torrents in list to run group actions (`space` to mark and move to next torrent, `V` to mark all/clear, `Esc` to clear marks before filters) [#164](https://github.com/anlar/tewi/pull/164)
- Show names of torrents in remove confirmation
- Add publishing release to PyPI from GitHub Actions
- Add filtering torrents by category and label (combined with other filters)
- Add copying magnet links of torrents to clipboard (`M`, marked torrents shown by filter one per line, or highlighted torrent), with v1 info hash also for qBittorrent hybrid torrents (v2-only torrents are skipped)
- Add several torrents at once in add dialog, one per line
- Merge web search results of the same torrent from several providers

### Changed

- Show torrent client version in top panel literally, without parsing it as markup, and remove control characters from it
- Don't overwrite existing config file with `--create-config`, create new one readable only by owner from the start
- Fix missing timeout of rTorrent HTTPS connection, so not responding daemon doesn't block refresh forever
- **Breaking:** Read config values literally, without "%" interpolation: "%" in password or API key no longer crashes startup showing part of the value in error; replace "%%" escapes with single "%"
- Remove control characters from notifications and torrent client preferences, which could contain text from torrent client and search providers
- Send torrent file downloaded from URL to Transmission directly, without writing it to temporary file
- Send Prowlarr API key in `X-Api-Key` header instead of URL query
- Warn on start if config file is accessible by other users
- Open search result links the same way as other links, also in browser when running with textual-serve
- Load search result details in background, so UI doesn't freeze while provider fetches extra details
- Change default search providers order to `yts`, `nekobt`, `nyaa`, `tpb`, `therarbg`, `bitsearch`, `knaben`, `limetorrents`, `torrentscsv` (specialized providers first), with Jackett and Prowlarr last when all providers are listed
- Fix web search results and details failing to show when a search provider doesn't report torrent size
- Fix search provider counts (seeders, leechers, downloads, size, files) sent as text being parsed as markup in search results
- Fix Jackett, Prowlarr, Bitmagnet, TPB, YTS and Nyaa search result details showing provider text as Markdown, which could add fake details or links with misleading text
- Remove control characters from search result details
- Apply search timeout (`--search-timeout`) to the whole search: providers not finished in time are skipped and reported, instead of delaying results
- Run torrent actions in background (UI doesn't freeze while torrent client process), and show failed action as warning instead of crashing
- **Breaking:** Move start/stop torrent from `space` to `p` and change torrent priority from `p` to `i` (`space` marks torrents)
- Fix `--filter` not accepting `checking` and `incomplete` states, and show error for invalid `filter` in config instead of failing to initialize application
- **Breaking:** Change key of "Checking" in filter dialog from `c` to `h`
- Fix setting category on Deluge silently doing nothing, as torrent hash wasn't sent to daemon
- Copy text to system clipboard in addition to terminal one (OSC 52), also when copying selected text in inputs, so copying works in terminals without OSC 52 support
- Don't use system clipboard in SSH session or textual-serve, where it belongs to machine running Tewi (copy only to terminal clipboard, don't fill link in add dialog)
- Read clipboard in add dialog in background, so not responding clipboard program doesn't freeze UI
- Fix duplicate web search results from different providers, which weren't merged when providers wrote the same info hash in different case or in Base32
- Show web search result details as plain text instead of Markdown
- Show all statistics in web search result details, with `-` for empty values
- Fix TPB search with several categories selected searching only the first one
- Fix TPB search failing completely on single invalid result
- Fix TPB search by category returning few results when other categories of the same TPB group (e.g. Movies for TV) took the result limit, and not finding PC and Mac games
- Fix Nyaa search with several categories selected searching only the first one, TV search not finding Live Action, and searching all categories when Nyaa has none of selected ones
- Label Nyaa own category as "Nyaa Category" in search result details, to distinguish it from common "Category"
- Load up to 100 Torrents-CSV search results (4 pages) instead of 25, as API ignores requested page size
- Fix YTS being searched when Movies category isn't selected
- Fix YTS search failing completely on single invalid result, and link to movie page built from movie ID not opening
- Add source type (BluRay, WEB) to YTS result titles, to distinguish torrents of the same quality, and map 480p ones to Movies/SD category
- Update YTS domain to yts.pw and magnet link trackers to ones recommended by YTS
- Fix Jackett search with several categories selected not filtering by category
- Search selected Jackett indexers with single request instead of one request per indexer
- Show error when all Jackett indexers failed to search instead of no results, and log failed indexers
- Fix Jackett search failing completely on single invalid result
- Don't log Jackett API key and don't show Jackett links containing it (poster, blackhole) in search result details
- Hide Jackett internal fields (category duplicate, volume factors, gain) in search result details and show HTML description as text
- Fix Bitmagnet search ignoring selected categories, which left few results after filtering
- Map Bitmagnet games to PC/Games, ebooks to Books/EBook, and torrents of unknown content to Other instead of hiding them when categories are selected
- Load up to 100 Bitmagnet search results instead of 50
- Load Bitmagnet search result details by exact info hash instead of searching it as text, and show torrent files in them
- Fix Bitmagnet search failing completely on single invalid result, show its timestamps in local time and episodes without duplication
- Fix Prowlarr search failing completely on single invalid result, and skipping results without indexer flags
- Skip Usenet results and indexers in Prowlarr search, as only torrents can be added
- Add Prowlarr results by Prowlarr download link instead of magnet link built from info hash, which has no trackers, so private torrents couldn't start
- Show Prowlarr search error message (e.g. all indexers unavailable) instead of HTTP status only
- Hide internal Prowlarr fields (protocol, comments link same as torrent page, zero IDs) in search result details, and don't show empty indexer info
- Fix IMDB links of Jackett and Prowlarr search results for IDs shorter than 7 digits
- Fix crash when Transmission or qBittorrent fails to add torrent, show error instead
- Fix total size of torrents missing in status bar while downloads are incomplete (e.g. "5.37 GB" shown instead of "5.37 GB / 10.74 GB")

### Removed

- **Breaking:** Remove `--debug` option and `debugpy` dev dependency
- Remove Torrentz2 search provider, as its site is shut down; `torrentz2` provider ID is now an alias for `bitsearch`, which serves the same torrent database
- **Breaking:** Remove hidden `--limit-torrents` option and `limit_torrents` config option, which had no effect
- Remove unmaintained Flatpak manifest

## [4.0.0] - 2026-11-06 - Lucky Handshake

### Added

- Add multiple sort orders for torrent list: press `m` in sort dialog to chain orders, where following orders break ties of previous ones (e.g. progress, then age)
- Add HTTPS connection to torrent client with `--tls` option or `https://` prefix in host, with certificate verification (`--no-tls-verify` to disable) and custom CA or self-signed certificate (`--ca-cert`)
- Show connection security badge in status line: `TLS`, `TLS unverified` or `No TLS` (for unencrypted connection to another machine)

### Changed

- **Breaking:** Restrict profile and theme names to letters, digits, `.`, `_` and `-`, starting with letter or digit: `--profile` with other name and config with such `[theme.NAME]` section stop with error, profile files with such names are not listed in `--profiles` and shell completion
- **Breaking:** Require Textual 3.1.0 or newer: older versions crash on notifications and, before 2.0, parse markup in labels which must show text literally (ANSI themes need Textual 8.2.5 or newer)
- **Breaking:** Require requests 2.33.0 or newer, as older versions have known vulnerabilities (CVE-2024-47081, CVE-2026-25645)
- **Breaking:** Require transmission-rpc 7.0.12 or newer and stop using its APIs removed in transmission-rpc 8
- Load Jackett indexers without searching trackers [#188](https://github.com/anlar/tewi/pull/188)
- Fix showing square brackets in torrent list name filter without extra backslash
- Show text from torrents, peers, trackers, search providers and torrent client literally, without parsing it as markup (prevent action injection on mouse click)
- Accept only magnet and HTTP(S) links from web search and open only HTTP(S) links, skip search results with malformed info hash, allow only HTTP(S) search provider URLs
- Limit torrent file download from URL: follow up to 5 redirects to magnet or HTTP(S) links only, download files up to 100 MiB, add torrents in background without blocking UI
- Log warning when password is sent to torrent client on another machine without TLS
- Warn in `--password` help that the value is visible in process list and shell history, suggest config file instead
- Limit size of caches for formatted values and peer countries, which grew during whole session
- Create config file and log directory accessible only by owner, restrict existing log directory too
- Remove control characters from text of torrents, peers, trackers and search results, so terminal escape sequences in them aren't passed to terminal
- Add 30 seconds timeout to Deluge requests, so not responding daemon doesn't block refresh forever
- Limit search provider responses to 20 MiB
- Pass search term to Bitmagnet as GraphQL variable instead of inserting it into query
- Fix crash of web search when provider returns several results with empty info hash
- Escape line breaks and control characters in log messages and indent tracebacks, so text from torrent clients and search providers can't forge log entries
- Don't write password and API keys to log on startup
- Mask passwords, API keys and passkeys of URLs and auth headers in log and notifications
- Don't load GeoIP database from current directory, as file with the same name was loaded from there and could run code, and don't fail on start if database can't be loaded
- Don't show GeoIP error text like `<invalid ip address>` as peer country
- Fix Deluge torrent details failing to load and showing client as offline when torrent has IPv6 peers
- Require setuptools 77.0 or newer to build package, as older versions don't support SPDX license field
- Replace geoip2fast with built-in peer country lookup by [ip-location-db](https://github.com/sapics/ip-location-db) data, downloaded on release: adds IPv6 peers, updates data from 2024, loads on first lookup in 25 ms and uses ~5 MiB of memory instead of ~40 MiB on start
- Show Deluge peer country by name instead of code
- Run tests on minimum supported dependency versions in CI

### Removed

- Remove `geoip2fast` dependency, replaced by built-in peer country lookup

## [3.1.0] - 2026-10-31 - Spectrum Rabbit

### Added

- Complete available profile names for `--profile` in shell completion
- Add custom color themes via `[theme.NAME]` config sections: define new theme (optionally based on existing one with `base` option) or override colors of built-in theme, using Textual color names or hex codes
- Add `--themes` CLI flag to print available themes (built-in and custom), one per line

### Changed

- Fix crash when opening torrent details on older Textual caused by unsupported column keys in files table
- Show connection status in top panel only when disconnected, as readable badge after host (connection dot colors were unreadable in some themes)
- Fix unreadable, faint or missing colors in non-default, light and ANSI themes: top and bottom panels, torrent status, badges, speeds, progress bar and secondary details (peers, speeds, sizes) on highlighted row, file priorities, freeleech tag, titles and key hints on panel borders, and inactive tabs in torrent details
- Make dialogs readable in all themes and stand out more: primary color borders, solid background and stronger dimming behind them
- `--profiles` prints a machine-readable list of profile names, one per line (nothing when no profiles exist)
- Unknown theme from `--theme` or config stops the app with error instead of falling back to default theme
- Config file created by `--create-config` ends with vim modeline for INI syntax highlighting

### Removed

- Remove `--list-themes` CLI flag, replaced by `--themes`

## [3.0.0] - 2026-10-18 - Hypersonic Paws

### Added

- Add rTorrent support (0.9.7 or newer), connecting directly via SCGI or via XML-RPC over HTTP when `--path` is set [#109](https://github.com/anlar/tewi/pull/109)
- Add sorting for web search results (`s` hotkey) [#180](https://github.com/anlar/tewi/pull/180)
- Add `Ctrl+F`/`Ctrl+B` (page down/up) and `Ctrl+D`/`Ctrl+U` (half page down/up) hotkeys to torrent list

### Changed

- Declare `requests` as an explicit dependency (used by Deluge client, previously installed only transitively via `qbittorrent-api`)
- `PgUp`/`PgDown` in torrent list now scroll by page instead of jumping to first/last item
- Ask for confirmation before starting or stopping all torrents
- Torrent list shows and sorts by size of selected files
- Torrent details show selected size and files count next to totals when some files are skipped
- Raise minimum required Textual version to 0.86.0 (themes support: theme selector and theme colors in torrent list)
- Fix torrent list scroll to highlighted item when switching to page with different number of torrents (e.g. moving up from last page left list scrolled to top)
- Rewrite torrent list with Textual line API (only visible lines are drawn) for much faster loading, updates and scrolling, and redesign it
- Default torrent list page size increased from 30 to 1000

## [2.6.0] - 2026-09-24 - Hop Collector

### Added

- Add `--print-completion` CLI flag to generate shell completion script for bash, zsh, or tcsh
- Support `${VAR_NAME}` environment variable references in config file values, useful for keeping secrets (passwords, API keys) out of the config file
- Ship a pre-generated bash completion script as a package data file
- Display general up/down speed limits
- Add multi-select for files tab (`space` to mark a file or folder, `V` to select/clear all, `Esc` to clear selection) for priority change actions [#163](https://github.com/anlar/tewi/issues/163)
- Display torrent client connection status in header bar (handle lost connection to the daemon and show time since last connection) [#134](https://github.com/anlar/tewi/issues/134)

### Changed

- Replace dark/light theme toggle (`d` hotkey) with theme selector (`T` hotkey), with startup theme configurable via `--theme` CLI flag and `theme` config option in `[ui]` section (default: `textual-dark`), and `--list-themes` CLI flag to list available themes
- Move development dependencies from extras to PEP 735 dependency groups (`dev`, `release`), with `build` and `twine` now declared for the release targets in `Makefile`
- Use `Client.free_space()` instead of deprecated `Session.download_dir_free_space` to get free space in Transmission client
- Show torrent comment in details panel as clickable link when it contains only an HTTP(S) URL
- Use `uv run python` instead of bare `python` in `Makefile` targets
- Pad torrent sizes in list to align them by separator
- Don't print terminal title escape sequence before early CLI exits (e.g. `--print-completion`, `--version`), which corrupted the printed output
- Improve torrent list rendering performance by skipping layout recalculation on label updates, sizing columns via CSS instead
- Align uploaded size and hide if it is empty in torrents list
- Fix search preset `indexers` option so a bare `prowlarr` or `jackett` entry enables all sub-indexers of that provider
- Right-align numeric columns in torrent details files, peers, and trackers tabs

## [2.5.0] - 2026-07-27 - Carrot Magnet

### Added

- Search presets to switch between predefined indexer and category combinations via `[search.preset.NAME]` config sections [#171](https://github.com/anlar/tewi/issues/171)
- Filter torrents by name via `F` hotkey in torrent list (`Esc` to clear filter) [#111](https://github.com/anlar/tewi/issues/111)
- Add torrent by a bare info hash, converted to a magnet link (Transmission, qBittorrent, Deluge)
- Add `--search-timeout` CLI flag and `timeout` config option in `[search]` section to configure the HTTP request timeout used by search providers (default: 30 seconds)

### Changed

- Fix incorrect size display in compact search view where integer sizes with trailing zeros (e.g. 680 MB) were stripped to wrong values (e.g. 68 MB)
- Bitmagnet: content details request timeout is now configurable via `--search-timeout` (previously hardcoded to 5 seconds)

## [2.4.1] - 2026-06-28 - Eientei Engine

### Changed

- qBittorrent: fix crash on torrent details view for qBittorrent 4.6.x [#174](https://github.com/anlar/tewi/issues/174)

## [2.4.0] - 2026-06-21 - Eientei Engine

### Added

- Add `--search-hide-zero-seeders` CLI flag and `hide_zero_seeders` config option to filter out dead torrents from search results [#167](https://github.com/anlar/tewi/issues/167)
- Add `PgUp`/`PgDown` hotkeys to torrent list [#165](https://github.com/anlar/tewi/issues/165)
- Show number of hidden search results with zero seeders
- Add compact mode for search results, toggled with `V` key and configurable via `--search-default-mode compact` [#166](https://github.com/anlar/tewi/issues/166)
- Limit and rotate log files by their size (`--log-size` CLI flag and `log_size` config option) (default: 10 MB, up to 3 files) [#170](https://github.com/anlar/tewi/issues/170)

### Changed

- Improve category detection for TV and Movies in Torrents-CSV search provider
- Update YTS provider domain proxy to .bz
- Update YTS provider API URL

## [2.3.1] - 2026-01-08 - Dozing Rabbit

### Changed

- Renamed PyPI package to `tewi-torrent` from `tewi-transmission`

## [2.3.0] - 2026-01-08 - Dozing Rabbit

### Added

- New torrent filters: `Checking` and `Incomplete`
- Add `--debug PORT` CLI option to start `debugpy` server for remote debugging

### Changed

- Resize table columns in torrent details panels for each torrent [#160](https://github.com/anlar/tewi/issues/160)
- Improve torrent/magnet link detection in Prowlarr search results
- Handle HTTP redirects when adding torrents from URLs, supporting both torrent file downloads and magnet link redirects (affects all clients: Transmission, qBittorrent, Deluge)
- Denser torrent card stats display with better formatting, compact labels, and visual separators
- Display torrent stats in compact view mode
- Refactor file/URL opening into a unified `open()` function in ui/util module for platform-specific handling
- Fix `DuplicateKey` error when torrent has multiple peers/trackers with the same host in details tables

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
- Command to list available search providers: `--list-search-providers` [#132](https://github.com/anlar/tewi/issues/132)

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
- Use short country names for qBittorrent peers
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
