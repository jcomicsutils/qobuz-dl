# qobuz-dl

A feature-rich command-line downloader for Qobuz.

## Installation

Using a venv keeps dependencies isolated while still giving you a `qobuz-dl`
command you can call from anywhere.

```bash
# 1. Create and activate the venv
git clone https://github.com/jcomicsutils/qobuz-dl.git
cd qobuz-dl
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies and the package in editable mode
pip install -r requirements.txt
pip install -e .

# 3. The `qobuz-dl` script is now at:
#      .venv/bin/qobuz-dl
#
#    Add that directory to your PATH so the command works in any terminal
#    (add this line to ~/.bashrc, ~/.zshrc, or equivalent):
export PATH="path/to/qobuz-dl/.venv/bin:$PATH"
```

After reloading your shell (`source ~/.bashrc` / `source ~/.zshrc`), you can
call `qobuz-dl` from any directory without activating the venv first.

## Prerequisites

You need three values from Qobuz:

| Value | Description |
|---|---|
| `app_id` | Qobuz application ID |
| `secret` | Qobuz application secret |
| `auth_token` | Your Qobuz user auth token |

You can find `app_id` and `secret` using [Qobuz-AppID-Secret-Tool](https://github.com/QobuzDL/Qobuz-AppID-Secret-Tool). The `auth_token` can be found on the [official Qobuz website](https://play.qobuz.com/) (premium account required). 

## Quick Start

```bash
# 1 - run the interactive wizard
qobuz-dl setup

# 1b - install shell completions (Fish / Bash / Zsh)
qobuz-dl completions --install

# 2 - search
qobuz-dl search "bod [包家巷]"
qobuz-dl search "Dear Diary," -t albums
qobuz-dl search "antiselytism" -t tracks

# 3 - download by URL
qobuz-dl dl https://open.qobuz.com/album/bvfy6ys14qrrc
qobuz-dl dl https://open.qobuz.com/track/229720604
qobuz-dl dl https://open.qobuz.com/artist/3767925

# 3 - or download by ID with a type prefix (ar-id, al-id, tr-id)
qobuz-dl dl al-id bvfy6ys14qrrc
qobuz-dl dl tr-id 229720604
qobuz-dl dl ar-id 3767925

# download multiple targets at once (URLs and prefixed IDs can be mixed)
qobuz-dl dl al-id bvfy6ys14qrrc ar-id 707261 https://open.qobuz.com/track/229720604
```

## Commands

### `setup`

Interactive configuration wizard. Covers credentials, quality,
folder/track templates, and per-field metadata toggles.

```bash
qobuz-dl setup
```

### `config`

View or set individual config values without running the wizard.

```bash
qobuz-dl config                          # print everything
qobuz-dl config download_dir             # print one value
qobuz-dl config download_dir ~/Music     # set a value
qobuz-dl config quality cd
qobuz-dl config folder_template "{main_artist}/{year} - {album} [{album_id}]"
```

#### Metadata field toggles

Use dot notation to read or write individual metadata field gates:

```bash
qobuz-dl config metadata_fields                   # show all fields and their state
qobuz-dl config metadata_fields.copyright         # show one field
qobuz-dl config metadata_fields.copyright false   # disable the copyright tag
qobuz-dl config metadata_fields.label false       # disable the label/publisher tag
qobuz-dl config metadata_fields.all true          # re-enable every field at once
qobuz-dl config metadata_fields.all false         # disable every field at once
```

### `search`

Search Qobuz for albums, tracks, or artists.

```bash
qobuz-dl search "bod [包家巷]"
qobuz-dl search "bod [包家巷]" -t albums -n 5
qobuz-dl search "bod [包家巷]" -t tracks
```

Options:
- `-n / --limit` - number of results per category (default: 10)
- `-t / --type` - filter to `albums`, `tracks`, `artists`, or `all`

### `dl`

Download albums, tracks, or full artist discographies.

Accepts full Qobuz URLs **or** IDs prefixed with `ar-id`, `al-id`, or
`tr-id`. A type prefix is always required for bare IDs - passing a raw ID
without a prefix will abort with an error.

```bash
# By URL
qobuz-dl dl https://open.qobuz.com/album/bvfy6ys14qrrc
qobuz-dl dl https://open.qobuz.com/artist/3767925

# By bare ID
qobuz-dl dl ar-id 707261          # entire artist discography
qobuz-dl dl al-id bvfy6ys14qrrc   # single album
qobuz-dl dl tr-id 229720604        # single track

# Mix URLs and prefixed IDs freely; batch as many targets as you like
qobuz-dl dl ar-id 707261 al-id bvfy6ys14qrrc https://open.qobuz.com/track/229720604

# Override quality just for this run
qobuz-dl dl al-id bvfy6ys14qrrc -q cd

# Custom download directory (one-off)
qobuz-dl dl ar-id 707261 -d ~/Desktop/NewAlbums

# Custom folder & track name templates
qobuz-dl dl al-id bvfy6ys14qrrc \
  -F "{main_artist}/{year} - {album} [{album_id}]" \
  -f "{track:02d}. {title} [{track_id}]"

# Skip cover art and metadata
qobuz-dl dl al-id bvfy6ys14qrrc --no-cover --no-metadata
```

Options:

| Flag | Description |
|---|---|
| `-d / --dir` | Override the download root directory |
| `-q / --quality` | `mp3`, `cd`, `hi-res`, `hi-res-192` |
| `-F / --folder-template` | Folder naming template |
| `-f / --track-template` | Track filename template (extension auto-added) |
| `--no-metadata` | Skip all metadata / tag embedding |
| `--no-cover` | Skip saving `cover.jpg` to disk |
| `--no-skip` | Re-download even if the file already exists |

### `completions`

Generate and install shell tab-completion scripts so flags and subcommands
are suggested as you type.  Supports Fish, Bash, and Zsh.

```bash
# Auto-detect your shell and install in one step
qobuz-dl completions --install

# Explicit shell
qobuz-dl completions --shell fish --install
qobuz-dl completions --shell bash --install
qobuz-dl completions --shell zsh  --install

# Print the raw script to stdout (pipe it wherever you like)
qobuz-dl completions --shell fish --print-only
```

After installing, restart your shell (or source the file as instructed) and
Tab will complete subcommands, flags, quality choices, search types, and more.

**Manual activation** (if the installer doesn't fit your setup):

| Shell | Command |
|---|---|
| Fish | `_QOBUZ_DL_COMPLETE=fish_source qobuz-dl > ~/.config/fish/completions/qobuz-dl.fish` |
| Bash | Add `eval "$(_QOBUZ_DL_COMPLETE=bash_source qobuz-dl)"` to `~/.bashrc` |
| Zsh  | Add `eval "$(_QOBUZ_DL_COMPLETE=zsh_source  qobuz-dl)"` to `~/.zshrc`  |

### `info`

Show metadata about an album or track without downloading anything.

```bash
qobuz-dl info https://open.qobuz.com/album/bvfy6ys14qrrc
qobuz-dl info https://open.qobuz.com/track/229720604
```

## Template Variables

Templates use Python's `str.format()` syntax.

### Folder template (`folder_template`)

| Variable | Example | Notes |
|---|---|---|
| `{artist}` | `bod [包家巷] • Émonie Fay Chetwin` | Combined list of all contributing artists |
| `{main_artist}` | `bod [包家巷]` | Only the primary album artist |
| `{album}` | `the death of all narratives` | |
| `{year}` | `2023` | |
| `{genre}` | `Electronic • Dance` | |
| `{label}` | `2465727 Records DK` | |
| `{quality}` | `FLAC 24bit 44.1kHz` | |
| `{artist_id}` | `3767925` | Prevents collisions between artists sharing a name |
| `{album_id}` | `k089kflmrltwc` | Prevents collisions between albums sharing a name |

### Track filename template (`track_template`)

| Variable | Example | Notes |
|---|---|---|
| `{track}` | `1` | |
| `{track:02d}` | `01` | Zero-padded |
| `{disc}` | `1` | |
| `{title}` | `the death of all narratives` | |
| `{artist}` | `bod [包家巷] • Émonie Fay Chetwin` | |
| `{album}` | `the death of all narratives` | |
| `{year}` | `2023` | |
| `{track_id}` | `229720604` | Prevents collisions between tracks sharing a name |

### Examples

```bash
# Artist > Year - Album > 01 - Title.flac
qobuz-dl config folder_template "{main_artist}/{year} - {album}"
qobuz-dl config track_template  "{track:02d} - {title}"

# Include IDs to guarantee unique filenames
qobuz-dl config folder_template "{main_artist}/{album} ({year}) [{album_id}]"
qobuz-dl config track_template  "{track:02d} - {title} [{track_id}]"

# Flat folder with disc prefix
qobuz-dl config folder_template "{main_artist} - {album}"
qobuz-dl config track_template  "{disc}-{track:02d} {title}"

# Genre subfolder
qobuz-dl config folder_template "{genre}/{main_artist}/{album} ({year})"
```

## Metadata Fields

When `embed_metadata` is `true`, qobuz-dl writes tags to every downloaded
file. Each field can be individually toggled so you embed only what you want.

| Field | FLAC tag | MP3 ID3 tag | Description |
|---|---|---|---|
| `title` | `TITLE` | `TIT2` | Track title |
| `artist` | `ARTIST` | `TPE1` | Track / performing artist |
| `album_artist` | `ALBUMARTIST` | `TPE2` | Album artist |
| `album` | `ALBUM` | `TALB` | Album title |
| `track_number` | `TRACKNUMBER` | `TRCK` | Track number |
| `disc_number` | `DISCNUMBER` | `TPOS` | Disc number |
| `date` | `DATE` | `TDRC` | Full release date (YYYY-MM-DD) |
| `year` | `DATE` | `TDRC` | Release year |
| `genre` | `GENRE` | `TCON` | Genre |
| `label` | `LABEL` | `TPUB` | Record label / publisher |
| `copyright` | `COPYRIGHT` | `TCOP` | Copyright string |
| `isrc` | `ISRC` | `TSRC` | ISRC code |
| `upc` | `BARCODE` | *(not set)* | Album UPC / barcode |
| `cover` | *(picture block)* | `APIC` | Cover art embedded **inside** the audio file |

> **`cover` vs `save_cover`** - `metadata_fields.cover` controls art embedded
> inside the audio file itself. The top-level `save_cover` setting controls
> whether a standalone `cover.jpg` is written alongside your tracks. They are
> completely independent.

### Managing metadata fields

```bash
# Show current state of every field
qobuz-dl config metadata_fields

# Disable fields you don't want
qobuz-dl config metadata_fields.copyright false
qobuz-dl config metadata_fields.label false
qobuz-dl config metadata_fields.upc false

# Re-enable everything at once
qobuz-dl config metadata_fields.all true

# Or walk through each field interactively during setup
qobuz-dl setup
```

## Quality Levels

| Key | Description |
|---|---|
| `mp3` | MP3 320 kbps |
| `cd` | FLAC 16-bit / 44.1 kHz |
| `hi-res` | FLAC 24-bit / up to 96 kHz |
| `hi-res-192` | FLAC 24-bit / up to 192 kHz *(default)* |

Qobuz will fall back to the highest quality available for a given track.

## Config File

Settings are stored at `~/.config/qobuz-dl/config.json`. All values
can be edited directly or via `qobuz-dl config KEY VALUE`.

```json
{
  "app_id": "...",
  "auth_tokens": ["..."],
  "secret": "...",
  "download_dir": "~/Music/Qobuz",
  "quality": "hi-res-192",
  "folder_template": "{artist}/{album} ({year}) [{quality}]",
  "track_template": "{track:02d} - {title}",
  "multi_disc": true,
  "save_cover": true,
  "embed_metadata": true,
  "metadata_fields": {
    "title":        true,
    "artist":       true,
    "album_artist": true,
    "album":        true,
    "track_number": true,
    "disc_number":  true,
    "date":         true,
    "year":         true,
    "genre":        true,
    "label":        true,
    "copyright":    true,
    "isrc":         true,
    "upc":          true,
    "cover":        true
  },
  "skip_existing": true,
  "socks5_proxy": "",
  "include_version": true,
  "force_main_album_artist": false
}
```

## SOCKS5 Proxy

Uncomment `PySocks` in `requirements.txt`, reinstall, then:

```bash
qobuz-dl config socks5_proxy VALUE
```

## Notes

- Downloads tracks as-is from Qobuz (FLAC or MP3). No re-encoding is performed,
  so no FFmpeg dependency is required.
- Metadata is embedded using [mutagen](https://mutagen.readthedocs.io/) (FLAC
  Vorbis comments or ID3 for MP3).
- Multi-disc albums are automatically saved into `Disc 1/`, `Disc 2/` subfolders
  (configurable with `multi_disc`).
- Already-downloaded files are skipped by default (`skip_existing = true`).
