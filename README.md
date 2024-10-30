<div align="center">
  <a href="https://github.com/anlar/tewi">
    <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-logo.png" alt="Tewi logo" width="100">
  </a>

  <h1>Tewi</h1>

  <p>Text-based interface for the Transmission BitTorrent daemon</p>
</div>

## About

![Tewi Screen Shot](https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-1.png)

<p align="center">
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-2.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-3.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-4.png" width="200"/>
  <img src="https://raw.githubusercontent.com/anlar/tewi/refs/heads/master/docs/images/tewi-screenshot-5.png" width="200"/>
</p>

Tewi is a TUI (text user interface) interface for the Transmission BitTorrent daemon.

Features:

- Connect to Transmission daemon by its credentials
- Browse torrents list
- Different view modes: card, compact, oneline
- Display torrent details: overview, files, trackers, peers
- Add new torrents
- Torrent actions: start/pause, remove/trash, verify, reannounce
- View and toggle Turtle Mode
- View Transmission session statistics
- Dark and light color themes

### Built With

* [Python 3](https://www.python.org/)
* [Textual](https://textual.textualize.io/)
* [transmission-rpc](https://github.com/Trim21/transmission-rpc)

## Getting Started

### Prerequisites

Tewi requires Python 3.10+.

### Installation

Recommended way to install is to use `pipx` or `pip`:

```
$ pipx install tewi-transmission
```

## Usage

Launch Tewi from command line:

```
$ tewi
```

By default it connects to Transmission daemon on http://localhost:9091. To change these settings
you could specify your connection details:

```
$ tewi --host XXXX --port XXXX
```

Check other command line options using help command:

```
$ tewi --help
```

View available hot-keys in Tewi by pressing `?` key.

## Roadmap

See the [open issues](https://github.com/anlar/tewi/issues) for a full list of proposed features (and known issues).

## Contributing

Feel free to open bug reports and send pull requests.

## License

Distributed under the GPL3+ license. See `LICENSE.txt` for more information.

