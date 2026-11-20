# AGENTS.md

Tewi is a Textual-based TUI for BitTorrent clients (Transmission,
qBittorrent, Deluge, rTorrent). Python 3.10+, managed with `uv`.

## Commands

- `make fix` - format code and auto-fix lint issues (ruff)
- `make auto-test` - lint, run all tests and smoke-run the app against
  every client (requires Docker)
- `make test-unit` - run tests that don't need a torrent client daemon

After completing changes run `make fix` and `make auto-test`; if Docker is
not available, run `make test-unit` instead of `make auto-test`.

## Layout

- `src/tewi/torrent/` - client abstraction: `base.py` (abstract client),
  `factory.py`, `clients/` (one module per client), `models.py` (DTOs)
- `src/tewi/search/` - web search: `base.py` (abstract provider),
  `providers/`
- `src/tewi/ui/` - `panel/`, `dialog/`, `widget/`, `messages.py`
- `tests/` - pytest; integration tests marked `@pytest.mark.integration`

## Conventions

- Max line length 80; follow ruff config in `ruff.toml`
- Use type hints for function signatures and class attributes; prefer
  modern syntax (`list[str]`, `X | None`) over `typing.List`/`Optional`
- Docstrings use Google style (`Args:`, `Returns:`)
- Sizes are in bytes, speeds in bytes/second
- DTOs are frozen dataclasses
- Features not supported by every client are gated via `capable()`
- Blocking client/network calls run in `@work(thread=True)` workers
- Logging: module-level `logger = get_logger()` from `util/log.py`; mark
  client calls and hot UI paths with `@log_time`
- Remote text (torrent/file names, peers, trackers, search results) must be
  wrapped with `plain_text()` from `ui/util.py` before display, so it is
  never parsed as Rich markup
- Messages in `ui/messages.py`: requests named `XxxCommand`, state change
  notifications named `XxxEvent`
- Styles go to `app.tcss`, not widget `DEFAULT_CSS`
- Keybinding descriptions use `"[Category] Description"` format

## Changelog

Add every change to `CHANGELOG.md` under **Unreleased**, after existing
entries (Keep a Changelog format). Start entries with a verb ("Add ...",
"Fix ..."); prefix breaking changes with `**Breaking:**`.
