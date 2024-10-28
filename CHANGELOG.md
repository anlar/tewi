# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add verifying status to state panel statistics [#37](https://github.com/anlar/tewi/issues/37)
- Add action to save screenshot [#42](https://github.com/anlar/tewi/issues/42)

### Changed

- Hide statuses with zero torrents from state panel [#36](https://github.com/anlar/tewi/issues/36)
- Dependencies: bump textual from 0.85.0 to 0.85.1 [#35](https://github.com/anlar/tewi/issues/35)

### Removed

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
