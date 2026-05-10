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
folder/track templates, quality fallback, and per-field metadata toggles.

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

#### Quality fallback

```bash
qobuz-dl config quality_fallback true
qobuz-dl config quality_fallback_path "hi-res-192, hi-res, cd"
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

# By prefixed ID
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

# Preview what would be downloaded without writing any files
qobuz-dl dl al-id bvfy6ys14qrrc --dry-run

# Skip cover art and metadata
qobuz-dl dl al-id bvfy6ys14qrrc --no-cover --no-metadata

# Override retry count for this run
qobuz-dl dl al-id bvfy6ys14qrrc -r 5

# Override the Album Artist tag for this run
qobuz-dl dl al-id bvfy6ys14qrrc --override-main-artist "Various Artists"

# Pin a single artist ID across all albums/tracks in this batch
qobuz-dl dl al-id bvfy6ys14qrrc al-id xyz --override-artist-id
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
| `--dry-run` | Preview what would be downloaded — no files written |
| `-r / --retries` | Override retry count on network failure |
| `--override-main-artist` | Override the Album Artist tag for this run |
| `--override-artist-id` | Pin one artist ID across all downloads in this batch |

### `info`

Show metadata about an album or track without downloading anything.

```bash
qobuz-dl info https://open.qobuz.com/album/bvfy6ys14qrrc
qobuz-dl info https://open.qobuz.com/track/229720604
qobuz-dl info al-id bvfy6ys14qrrc
qobuz-dl info tr-id 229720604
```

### `completions`

Generate and install shell tab-completion scripts so flags and subcommands
are suggested as you type. Supports Fish, Bash, and Zsh.

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

## Quality Fallback

Some tracks have corrupt hi-res files on Qobuz's CDN — the server declares
a valid `Content-Length` but drops the connection after exactly 1 byte on
every attempt. This is distinct from an ordinary network error and cannot be
resolved by retrying the same quality.

When quality fallback is enabled, qobuz-dl detects this specific pattern and
automatically retries the track at the next lower quality in the configured
fallback path. Ordinary network errors (timeouts, DNS failures, connection
resets) never trigger fallback so that transient issues don't cause silent
quality downgrades.

Enable and configure via setup or config:

```bash
qobuz-dl config quality_fallback true
qobuz-dl config quality_fallback_path "hi-res-192, hi-res, cd"
```

Or run `qobuz-dl setup` and answer the fallback prompt after the quality
selection.

### Fallback path

The path is an ordered comma-separated list of quality keys from highest to
lowest. The download starts at your configured quality (or the `-q` override)
and walks down the list until one succeeds or the list is exhausted. If the
entire path fails with CDN errors, the track is handled according to
`on_final_failure`.

| Key | Description |
|---|---|
| `hi-res-192` | FLAC 24-bit / up to 192 kHz |
| `hi-res` | FLAC 24-bit / up to 96 kHz |
| `cd` | FLAC 16-bit / 44.1 kHz |
| `mp3` | MP3 320 kbps |

**Example paths:**

```bash
# Stop at CD quality — never fall back to MP3
qobuz-dl config quality_fallback_path "hi-res-192, hi-res, cd"

# Only fall back one step
qobuz-dl config quality_fallback_path "hi-res-192, hi-res"

# Accept any quality
qobuz-dl config quality_fallback_path "hi-res-192, hi-res, cd, mp3"
```

Fallback is **disabled by default** (`quality_fallback = false`). When a
fallback quality is used, the downloaded filename reflects the actual file
extension (always `.flac` except for MP3) and a note is printed next to the
track confirming the quality used.

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
| `date` | `DATE` | `TDRC` | Full release date (YYYY-MM-DD). When enabled, `year` is not written separately. |
| `year` | `DATE` | `TDRC` | Release year only. Written only when `date` is disabled. |
| `genre` | `GENRE` | `TCON` | Genre |
| `label` | `LABEL` | `TPUB` | Record label / publisher |
| `copyright` | `COPYRIGHT` | `TCOP` | Copyright string |
| `isrc` | `ISRC` | `TSRC` | ISRC code |
| `upc` | `BARCODE` | *(not set)* | Album UPC / barcode |
| `cover` | *(picture block)* | `APIC` | Cover art embedded **inside** the audio file |

> **`date` vs `year`** — both fields write to the same underlying tag (`DATE` / `TDRC`). When `date` is enabled it wins and `year` is not written. Only if `date` is disabled will `year` be written instead.

> **`cover` vs `save_cover`** — `metadata_fields.cover` controls art embedded inside the audio file itself. The top-level `save_cover` setting controls whether a standalone `cover.jpg` is written alongside your tracks. They are completely independent.

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

## Cover Art

Cover art is controlled by two independent settings:

- **`save_cover`** — saves `cover.jpg` alongside the downloaded tracks.
- **`metadata_fields.cover`** — embeds cover art inside each audio file.

Both can be active at once. Each uses its own size setting:

| Config key | Default | Description |
|---|---|---|
| `cover_size` | `original` | Size of the `cover.jpg` saved to disk |
| `embed_cover_size` | `original` | Size of the art embedded inside audio files |
| `embed_cover_oversize_action` | `use_large` | What to do when the original image exceeds the 16 MiB FLAC limit: `use_large` falls back to 600×600, `skip` omits embedded art for that track |

Available sizes: `thumbnail` (50×50), `small` (230×230), `large` (600×600), `original` (typically 1400×1400 or 3000×3000).

```bash
qobuz-dl config cover_size large
qobuz-dl config embed_cover_size large
qobuz-dl config embed_cover_oversize_action skip
```

## Filename & Folder Truncation

Long album or artist names can exceed filesystem limits (255 bytes on Linux/macOS,
often less on SMB/NAS shares). qobuz-dl truncates at the path-segment level
(individual folder names and filenames, not the full path).

| Config key | Default | Description |
|---|---|---|
| `truncate_filename` | `true` | Enable truncation of track filenames |
| `filename_max_bytes` | `255` | Maximum byte length for a filename (including extension) |
| `filename_truncate_pos` | `end` | Where to cut: `end` removes a suffix, `middle` removes the centre |
| `filename_truncate_marker` | `...` | String inserted at the cut point |
| `truncate_folder` | `true` | Enable truncation of folder name segments |
| `folder_max_bytes` | `255` | Maximum byte length for a single folder segment |
| `folder_truncate_pos` | `end` | Where to cut: `end` or `middle` |
| `folder_truncate_marker` | *(empty)* | String inserted at the cut point |

All settings are configurable via `qobuz-dl setup` or `qobuz-dl config KEY VALUE`.

> **Byte counts, not character counts.** CJK characters and accented letters
> each occupy 2–4 bytes in UTF-8, so a name can hit the limit with far fewer
> than 255 visible characters. The truncation logic always cuts on valid
> UTF-8 boundaries so filenames are never corrupted.

## Network & Retry Behaviour

| Config key | Default | Description |
|---|---|---|
| `retries` | `3` | Number of retry attempts after a failed download |
| `on_final_failure` | `delete_partial` | What to do after all retries are exhausted: `keep_partial`, `delete_partial`, or `delete_album` |
| `socks5_proxy` | *(empty)* | SOCKS5 proxy address (`host:port`) |

`on_final_failure` options:

- **`keep_partial`** — the partial file stays on disk; rerunning the same command will skip already-completed tracks and retry only the failed one.
- **`delete_partial`** — the incomplete file is deleted and the download continues with the next track.
- **`delete_album`** — all files downloaded for the current album are deleted and the folder is removed.

The per-run retry count can be overridden with `-r / --retries` on the `dl` command.

## Title & Artist Formatting

| Config key | Default | Description |
|---|---|---|
| `include_version` | `true` | Append edition/version to album and track titles, e.g. `(Remastered)` |
| `strip_feat_from_album_title` | `false` | Remove `(feat. …)` patterns from album titles |
| `strip_feat_from_track_title` | `false` | Remove `(feat. …)` patterns from track titles (only when Qobuz marks a FeaturedArtist role) |
| `force_main_album_artist` | `false` | Set the Album Artist tag to the primary artist only, instead of all contributing artists |

```bash
qobuz-dl config include_version false
qobuz-dl config strip_feat_from_track_title true
qobuz-dl config force_main_album_artist true
```

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
  "cover_size": "original",
  "embed_cover_size": "original",
  "embed_cover_oversize_action": "use_large",
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
  "retries": 3,
  "on_final_failure": "delete_partial",
  "quality_fallback": false,
  "quality_fallback_path": ["hi-res-192", "hi-res", "cd"],
  "socks5_proxy": "",
  "include_version": true,
  "force_main_album_artist": false,
  "strip_feat_from_album_title": false,
  "strip_feat_from_track_title": false,
  "truncate_filename": true,
  "filename_truncate_pos": "end",
  "filename_truncate_marker": "...",
  "filename_max_bytes": 255,
  "truncate_folder": true,
  "folder_truncate_pos": "end",
  "folder_truncate_marker": "",
  "folder_max_bytes": 255
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
- Non-streamable tracks are automatically skipped with a warning.
- Verbose/debug output (API calls, URL signing, file paths, metadata decisions)
  is available via the global `--verbose` / `-v` flag:
  ```bash
  qobuz-dl --verbose dl al-id bvfy6ys14qrrc
  qobuz-dl -v search "Merzbow"
  ```
