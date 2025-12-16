<div align="center">
  <a href="https://github.com/anlar/tewi">
    <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-logo.png" alt="Tewi logo" width="100">
  </a>

  <h1>Tewi</h1>

  <p>Text-based interface for BitTorrent clients (Transmission, qBittorrent, Deluge)</p>
</div>

## About

![Tewi Screen Shot](https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-1.png)

<p align="center">
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-2.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-3.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-4.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-5.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-6.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-7.png" width="200"/>
</p>

Tewi is a TUI (text user interface) for BitTorrent clients, supporting
Transmission, qBittorrent and Deluge daemons.

Features:

- Connect to Transmission/qBittorrent/Deluge daemon by credentials
- Browse torrents list
- Different view modes: card, compact, oneline
- Display torrent details: overview, files, trackers, peers
- View and edit torrent categories and labels
- Add new torrents
- Torrent actions: start/pause, remove/trash, verify, reannounce, change
  priority
- View and toggle alternative speed limits
- View session statistics
- View torrent client preferences
- Dark and light color themes
- Search torrents on popular trackers (built-in search providers,
  [Jackett](https://github.com/Jackett/Jackett),
  [Prowlarr](https://github.com/Prowlarr/Prowlarr) and
  [bitmagnet](https://github.com/bitmagnet-io/bitmagnet)
  integrations)
- Support for configuration files and different configuration profiles

### Built With

* [Python 3](https://www.python.org/)
* [Textual](https://textual.textualize.io/)
* [transmission-rpc](https://github.com/Trim21/transmission-rpc)
* [qbittorrent-api](https://github.com/rmartin16/qbittorrent-api)
* [pyperclip](https://github.com/asweigart/pyperclip)

## Getting Started

### Prerequisites

Tewi requires Python 3.10+.

### Installation

Recommended way to install is to use `pipx`, `pip`, or `uv`:

```
$ pipx install tewi-transmission
```

```
$ pip install tewi-transmission
```

```
$ uv tool install tewi-transmission
```

## Usage

Launch Tewi from command line:

```
$ tewi
```

By default it connects to Transmission daemon on http://localhost:9091. To
change these settings you could specify your connection details:

```
$ tewi --host XXXX --port XXXX
```

To connect to qBittorrent instead of Transmission:

```
$ tewi --client-type qbittorrent --port 8080
```

Check other command line options using help command:

```
$ tewi --help
```

View available hot-keys in Tewi by pressing `?` key.

## Roadmap

See the [open issues](https://github.com/anlar/tewi/issues) for a full list of
proposed features (and known issues).

## Contributing

Feel free to open bug reports and send pull requests.

## License

Distributed under the GPL3+ license. See `LICENSE.txt` for more information.

