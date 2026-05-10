# TODO — qobuz-dl feature backlog

Items are grouped by priority. Each entry includes a brief rationale and,
where relevant, implementation hints.

---

## High priority

### Playlist & favourites support
- Add `pl-id <id>` prefix and Qobuz playlist URL recognition
  (`https://open.qobuz.com/playlist/<id>`)
- Call `playlist/get` to enumerate tracks, then reuse `download_single_track`
  for each one, grouped into a sensibly-named output folder
- Also consider `user/library/getAlbums` to let users dump their entire
  "My Albums" favourites list in one command
- Relevant CLI addition: `qobuz-dl dl pl-id 12345678`

### Resume on network failure
- Build the previous feature (Retry) in a way that resuming can be added in the future, in case user picks to keep partial file. Or if user deleted only the partial file, rerunning same album would download only the missing track.

---

## Medium priority

### Batch input from a file (`--file`)
- Add `-i / --file PATH` to `dl` that reads one URL or prefixed ID per line
  (blank lines and `#` comments ignored)
- Lines are merged with any additional inline targets before processing
- Example file format:
  ```
  # Current 93
  al-id 0060253780948
  https://play.qobuz.com/album/xyz
  ar-id 707261
  ```

### `comment` and `lyrics` metadata fields
- Add `comment` and `lyrics` to `METADATA_FIELDS` (both default `False`)
- FLAC: write `COMMENT` and `LYRICS` Vorbis comments
- MP3: write `COMM` (ID3 comment frame) and `USLT` (unsynchronised lyrics frame)
- Source: call `track/getLyrics` when the field is enabled; gracefully skip
  if the endpoint returns nothing for that track

### `total_tracks` and `total_discs` tags
- Extend `embed_flac_metadata` to write `TOTALTRACKS` and `TOTALDISCS`
  Vorbis comments
- Extend `embed_mp3_metadata` to write `TRCK` in `n/total` format (e.g. `03/12`)
  and `TPOS` in `d/total` format
- Values are already available at embed time (`len(tracks)`, `len(disc_nos)`)

### Configurable cover art filename and resolution
- Add a `cover_filename` config key (default `cover.jpg`; common alternatives:
  `folder.jpg`, `AlbumArt.jpg`) so the saved file matches what the user's
  media player or NAS expects
- Add a `cover_size` config key accepting `small`, `large`, or `org` (default)
  to control which Qobuz image URL variant is fetched; avoids pulling 30 MB
  artwork for users who don't need it

### Artist discography release-type filter
- Add a `--release-type` option to `dl` (and a `default_release_types` config
  key) accepting a comma-separated subset of `album`, `epSingle`, `live`,
  `compilation`
- Default remains all four types to preserve current behaviour
- Example: `qobuz-dl dl ar-id 707261 --release-type album,epSingle`

### Parallel track downloads (`--concurrency`)
- Add `-j / --concurrency N` flag (default `1`) and matching config key
- Use `concurrent.futures.ThreadPoolExecutor` with `N` workers inside
  `download_album`; each worker calls `download_single_track`
- Keep the Rich progress bar working by pre-adding all tasks before the
  executor starts, then completing them as futures resolve
- Cap the default at `3` in the setup wizard to avoid hammering the API

### `qobuz-dl retag <path> <id/url>` subcommand
- New subcommand that walks a directory of already-downloaded audio files,
  looks up the track/album from the given id or url, and re-embeds tags
  according to the current config
- Useful after changing `metadata_fields` preferences without wanting to
  re-download hundreds of files
- Should support dry-run mode to preview what would change before writing

---

## Lower priority / nice-to-have

### `composer` and `performer` metadata fields
- Add `composer` and `performer` to `METADATA_FIELDS` (default `True`)
- FLAC: `COMPOSER` and `PERFORMER` Vorbis comments
- MP3: `TCOM` (composer) and `TPE3` (conductor/performer) ID3 frames
- Source data is in `track["composer"]["name"]` and
  `track["performer"]["name"]` — both are already fetched

### M3U playlist generation
- Add a `save_playlist` config key (default `False`) and `--playlist` / `--no-playlist`
  flags on `dl`
- After all tracks in an album are downloaded, write `playlist.m3u8` into the
  album folder listing the relative paths of all successfully downloaded files
  in track order
- Makes it trivial to open the album in any media player without importing

### Multiple auth token rotation with failure detection
- The API client already picks a random token from `auth_tokens` each request
- Extend this to track which tokens are returning 401/403 errors and temporarily
  remove them from the pool, logging a warning when a token fails
- Persist a "bad tokens" list across runs so a suspended account doesn't keep
  being tried; clear it when the user runs `setup` or `config auth_tokens`

### Download history / deduplication log
- Maintain a lightweight SQLite or JSONL log of successfully downloaded
  album/track IDs at `~/.config/qobuz-dl/history.db`
- Add a `--no-history` flag to `dl` to bypass it
- Add a `qobuz-dl history` subcommand to query or clear the log
- Prevents re-downloading the same release when it appears in multiple artist
  discographies or is passed multiple times in a batch

### `qobuz-dl ls` / library listing subcommand
- Call `user/library/getAlbums` and `user/library/getTracks` to list the
  user's Qobuz favourites without downloading anything
- Output as a Rich table (matching `search` style) with URLs for easy piping
  into `dl`

### Progress persistence for large artist downloads
- When downloading a full discography, write a small state file
  (e.g. `~/.config/qobuz-dl/state/<artist_id>.json`) listing completed and
  failed album IDs
- If the command is interrupted and restarted with the same artist, skip
  already-completed albums without fetching them again from the API
- Clear the state file when all albums complete successfully

### Output format options for `search` and `info`
- Add a `--json` flag to `search` and `info` to emit machine-readable JSON
  instead of Rich tables; enables piping into `jq`, scripts, or other tools
- Add a `--url-only` shorthand to `search` that prints one URL per result
  line, ready to pipe directly into `dl`

### Config profiles
- Allow multiple named config profiles (e.g. `--profile lossless`,
  `--profile mp3-archive`) stored as separate JSON files under
  `~/.config/qobuz-dl/profiles/`
- `qobuz-dl config --profile NAME` selects a profile for read/write
- `qobuz-dl dl --profile NAME` loads that profile for the run
- Useful for switching between quality levels or download directories without
  running `setup` each time

---

## Bug fixes / correctness

### `format_bytes` type annotation
- `n /= 1024` reassigns an `int` binding to a `float`, but the parameter and
  loop variable are annotated `int`; mypy flags this
- Fix: annotate `n` as `float` from the start, or cast once before the loop

### `embed_metadata` override in `dl` is fragile
- `effective_cfg` correctly sets `embed_metadata = False` when `--no-metadata`
  is passed, but `get_meta_fields` receives the same dict by reference, so the
  override works by coincidence rather than by contract
- Fix: pass the resolved boolean explicitly as a parameter to `get_meta_fields`
  instead of relying on the shared dict mutation

### `date` / `year` field precedence undocumented
- In `embed_flac_metadata`, `year` is only written if `date` is disabled
  (they share the same `DATE` Vorbis comment); if both are `true`, `date` wins
  silently
- Fix: document this in the README's metadata fields table and in the `setup`
  wizard prompt, so user knows the hierarchy (YEAR is only written if DATE is
  not written) — now documented in README, but the setup wizard prompt could
  make it more explicit

### `download_album` rebuilds the filename to track downloaded files
- After `download_single_track` succeeds, `download_album` re-runs the
  `safe_format` / `clean_name` / `truncate_name` pipeline a second time to
  reconstruct the filename for its `downloaded_files` list
- This is redundant and fragile: if any formatting step is non-deterministic
  or changes, the reconstructed path could diverge from the actual file on disk
- Fix: have `download_single_track` return the resolved `Path` on success
  (or `None` on failure) instead of a plain `bool`; the album orchestrator
  collects those paths directly

### Non-streamable tracks silently omitted from dry-run
- In `download_album`, non-streamable tracks are filtered during the live
  download loop, but `dry_run_album` feeds the raw track list to
  `_dry_run_track_rows` without checking `track.get("streamable", True)`
- Fix: filter non-streamable tracks in `_dry_run_track_rows` (or before
  calling it) and show them in the dry-run table with a `[dim]not streamable[/]`
  action label so the preview matches what would actually happen

### `parse_targets` prefix scope crosses URL boundaries unexpectedly
- After a URL token, `current_prefix` is reset to `None`, which is correct
- However, if a prefix like `ar-id` is set and then a URL appears, the URL
  takes priority and the prefix is cleared — but only for that one token;
  the next bare ID after the URL will correctly raise
- This is correct behaviour but is not tested for the case where a prefix
  is set, a URL appears mid-stream, and then another bare ID follows
- Add a test: `("ar-id", "111", "https://…/album/xyz", "222")` — the `"222"`
  should raise because the URL reset the prefix
