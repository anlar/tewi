# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Tewi is a TUI (text user interface) for BitTorrent clients built with Python
and Textual. It supports multiple BitTorrent client daemons: Transmission,
qBittorrent, and Deluge.

**Tech Stack:**
- Python 3.10+
- Textual (TUI framework)
- transmission-rpc, qbittorrent-api, deluge-client (client libraries)
- pytest (testing)
- flake8 (linting)

## Common Commands

### Development

To perform linting, test execution and test run application execute single
command:

```bash
make auto-test
```

Always execute it after completed changes on code-base.

## Architecture

### Multi-Client Architecture

The codebase is designed around a **factory pattern with abstract base class**
to support multiple BitTorrent clients:

1. **Abstract Layer** (`service/base_client.py`):
   - `BaseClient`: Abstract base class defining the interface all clients must
     implement
   - Common DTOs: `ClientMeta`, `ClientStats`, `ClientSession`
   - All methods are abstract and must be implemented by concrete clients

2. **Factory** (`service/client_factory.py`):
   - `create_client()`: Factory function that instantiates the appropriate
     client based on `client_type` parameter
   - Supported types: 'transmission', 'qbittorrent', 'deluge'

3. **Concrete Implementations**:
   - `TransmissionClient` (service/transmission_client.py)
   - `QBittorrentClient` (service/qbittorrent_client.py)
   - `DelugeClient` (service/deluge_client.py)

**When adding support for a new client:**
- Create a new class that inherits from `BaseClient`
- Implement all abstract methods
- Add instantiation logic to `create_client()` factory

### Search Provider Architecture

The app supports pluggable torrent search providers following an ABC pattern:

1. **Abstract Layer** (`service/search/base_provider.py`):
   - `BaseSearchProvider`: Abstract base class for search implementations
   - Required methods: `_search_impl(query)`, `short_name`, `full_name`
   - Built-in category detection from torrent names

2. **Concrete Providers**:
   - `TorrentsCSVProvider`, `YTSProvider`, `TPBProvider`, `NyaaProvider`
   - Located in `service/search/` directory

**When adding a new search provider:**
- Inherit from `BaseSearchProvider`
- Implement `_search_impl(query)` returning `list[SearchResultDTO]`
- Implement `short_name` and `full_name` properties
- The base class handles category refinement automatically

### Client Capability Detection

Clients implement feature detection via the `capable()` method:

- Method signature: `capable(capability_code: str) -> bool`
- UI conditionally displays/disables features based on capability
- Example: Transmission doesn't support categories
- Use this pattern when adding features that not all clients support

### Data Transfer Objects (DTOs)

All data structures are defined in `common.py` as immutable dataclasses:

- `TorrentDTO`: Torrent information for list views
- `FileDTO`: File information within torrents
- `CategoryDTO`: Category information
- `PeerDTO`, `TrackerDTO`: Peer and tracker information

**Important conventions:**
- All size fields are in **bytes**
- All speed fields are in **bytes/second**
- DTOs are frozen (immutable) for consistency

### Message-Based Communication

The app uses Textual's message passing system (`message.py`):

- **Commands**: User actions that trigger operations (e.g.,
  `AddTorrentCommand`, `RemoveTorrentCommand`)
- **Events**: Notifications of state changes (e.g., `TorrentRemovedEvent`,
  `FilterUpdatedEvent`)

Messages are posted to bubble up through the widget hierarchy and handled by
appropriate message handlers decorated with `@on()`.

### UI Structure

The UI follows a **three-tier hierarchy**:

1. **App** (`app.py`): Main application class, manages state and coordinates
   between UI and service layer
2. **Panels** (`ui/panel/`): Large sections of the UI (e.g., `listview.py`,
   `details.py`, `websearch.py`)
3. **Dialogs** (`ui/dialog/`): Modal dialogs for user input (e.g., `add.py`,
   `edit.py`, `confirm.py`)
4. **Widgets** (`ui/widget/`): Reusable components (e.g., `torrent_item.py`)

### Textual Framework Patterns

The app uses Textual's reactive system and widget patterns extensively:

**Reactive Attributes:**
- Use `reactive()` for state that triggers UI updates
- Example: `selected = reactive(False)` in `ui/widget/torrent_item.py:32`
- Optional `layout=True` parameter triggers layout recalculation on change

**Watch Methods:**
- Methods named `watch_<attribute>()` automatically trigger when reactive
  values change
- Example: `watch_selected()` adds/removes CSS classes in
  `ui/widget/torrent_item.py:77`
- Use for CSS class manipulation: `add_class()`, `remove_class()`

**Widget Base Classes:**
- `Static`: Base for custom widgets and panels
- `ListView`: Scrollable lists with vim-style bindings
- `ModalScreen[T]`: Generic dialog that returns typed value via `dismiss()`
- `DataTable`: Tables (extended as `VimDataTable` with vim keys)
- `Label`, `ProgressBar`: Simple display widgets

**Dialog/Screen Pattern:**
Consistent two-class structure for modal dialogs:
1. DialogClass(ModalScreen[ReturnType]): Manages lifecycle, bindings, and
   result handling
2. DialogWidget(Static): Contains actual UI composition in `compose()`
   method

Example from `ui/dialog/confirm.py`:
- `ConfirmDialog(ModalScreen[bool])`: Handles y/n bindings, calls
  `self.dismiss(True/False)`
- `ConfirmWidget(Static)`: Composes Label widgets for message display

**Custom Render Methods:**
- Override `render()` for custom display logic (e.g., `SpeedIndicator`)
- Return Rich renderables for styled output

### Keybinding Conventions

All panels and dialogs follow consistent keybinding patterns:

**Declaration:**
- `BINDINGS: ClassVar[list[BindingType]]` class attribute
- Each binding: `Binding(key, action, description)`
- Example: `Binding("y", "confirm", "[Confirmation] Yes")`

**Vim-Style Keys:**
- Navigation: `j/k` (down/up), `h/l` (left/right), `g/G` (home/end)
- Used throughout: ListView, DataTable, dialogs

**Action Methods:**
- Naming: `action_<name>()` for binding action "name"
- Example: `action_confirm()` handles binding with action="confirm"

**Binding Categories:**
- Description format: `"[Category] Description"` for help text grouping
- Categories appear in help dialog for better organization

### Configuration

Configuration is managed via `config.py`:
- Follows XDG Base Directory specification
- Config file location: `~/.config/tewi.conf` (or `$XDG_CONFIG_HOME/tewi.conf`)
- CLI arguments override config file settings
- Merged in `merge_config_with_args()`

## Testing

### Test Organization

- Unit tests: `tests/test_*.py`
- Integration tests: Marked with `@pytest.mark.integration`
- Test utilities: `tests/util/`

Run tests with `make auto-test` command.

### Key Test Files

- `test_config.py`: Configuration loading and merging
- `test_util_print.py`: Formatting utilities (sizes, speeds, times)
- `test_util_misc.py`: Miscellaneous utilities
- `test_search_providers_integration.py`: Web search integration tests
- `test_category_detection.py`: Automatic torrent categorization

### Async and Concurrency

The app uses Textual's work system for background operations:

**@work Decorator:**
- Use `@work(exclusive=True, thread=True)` for blocking I/O operations
- Example: `load_tdata()` in `app.py:174` runs in background thread
- Message handlers remain synchronous; work methods handle async tasks
- Threading used for client API calls (transmission-rpc, qbittorrent-api,
  deluge-client)

**Pattern:**
- UI remains responsive during long-running operations
- Work methods post messages when complete to update UI
- Don't block the main event loop with synchronous API calls

## Code Style

Always ensure that any Python code you write or modify:

- Follows PEP 8 style guidelines
- Follow flake8 code style rules
- Maximum code line length should be less than 80 symbols
- Has proper docstrings for functions and classes
- Uses type hints where appropriate
- Maintains consistent formatting

To execute linting use command: `make check`.

## Changelog

All changes should be added to `CHANGELOG.md` to **Unreleased** section after
already existing changes. Its format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Key Utilities

- `util/print.py`: Formatting functions for human-readable output (sizes,
  speeds, durations). Uses `@functools.cache` for performance.
- `util/misc.py`: General utilities
- `util/decorator.py`: Performance monitoring decorators
- `util/geoip.py`: GeoIP lookups for peer locations
- `util/data.py`: Data processing utilities (file tree building/flattening)

### Logging and Performance Monitoring

**Logging Setup:**
- Module-level logger: `logger = logging.getLogger('tewi')`
- Used throughout the codebase for debugging and monitoring

**Performance Monitoring:**
- `@log_time` decorator from `util/decorator.py`
- Automatically logs functions taking > 1ms
- Applied to critical paths: UI rendering, data updates, API calls
- Example: Used extensively in `ui/widget/torrent_item.py` for monitoring
  widget updates

## Version Management

Version is defined in `src/tewi/version.py` and dynamically read by setuptools
via `pyproject.toml`.

Project uses Semantic Versioning format.
