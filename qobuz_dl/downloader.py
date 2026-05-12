"""
downloader.py — Download pipeline: HTTP streaming, single-track download,
dry-run preview, and full album orchestration.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from .api import QobuzAPI
from .config import get_meta_fields
from .constants import (
    EXT_MAP,
    PREVIEW_DURATION,
    PREVIEW_DURATION_TOLERANCE,
    QUALITY_MAP,
    QUALITY_LABELS,
    QUALITY_ORDER,
)
from .metadata import embed_flac_metadata, embed_mp3_metadata, fetch_cover, fetch_cover_for_embed
from .utils import (
    apply_version_to_title,
    clean_name,
    console,
    dbg,
    get_artists,
    get_main_artist,
    get_quality_tag,
    get_year,
    safe_format,
    strip_feat_from_album_title,
    strip_feat_from_track_title,
    truncate_name,
)

# Matches the specific CDN-broken pattern: server declares a full Content-Length
# but drops the connection after exactly 1 byte.  This is distinct from ordinary
# network errors and is used to gate quality fallback so we don't silently
# downgrade on a simple connectivity blip.
_INCOMPLETE_READ_RE = re.compile(r"IncompleteRead\(1 bytes read")


# ─────────────────────────────────────────────────────────────────────────────
# Low-level HTTP streaming
# ─────────────────────────────────────────────────────────────────────────────

def stream_download(
    url: str,
    dest: Path,
    session: requests.Session,
    progress: Progress,
    task: TaskID,
    retries: int = 3,
    url_fetcher=None,
) -> Tuple[bool, bool]:
    """Stream *url* to *dest*, retrying up to *retries* times with exponential back-off.

    If *url_fetcher* is provided (a zero-argument callable returning a fresh URL
    string), it is called before each retry so each attempt uses a new signed URL.
    This matters because Qobuz/Akamai CDN URLs can be invalidated server-side
    after a failed transfer, causing every retry with the same URL to fail
    identically.

    Returns ``(success, cdn_broken)`` where *cdn_broken* is True when every
    network failure matched the ``IncompleteRead(1 bytes read, …)`` pattern —
    the signal that the CDN file itself is corrupt and a quality fallback should
    be tried.  Any other kind of error (timeout, DNS, OS write error) sets
    *cdn_broken* to False so that ordinary failures never trigger silent
    quality downgrades.
    """
    dbg(f"Streaming download → {dest}  (retries={retries})")
    dbg(f"  URL: {url}")
    last_exc: Optional[Exception] = None
    all_cdn_broken = True   # flipped False the moment any non-IncompleteRead error appears

    for attempt in range(retries + 1):
        if attempt > 0:
            delay = 2 ** attempt
            dbg(f"  Retry {attempt}/{retries} — waiting {delay}s after: {last_exc}")
            console.print(f"  [yellow]⟳ Retry {attempt}/{retries}[/] — waiting {delay}s…")
            time.sleep(delay)
            if url_fetcher is not None:
                try:
                    url = url_fetcher()
                    dbg(f"  Fresh URL obtained for retry {attempt}: {url}")
                except Exception as exc:
                    console.print(f"  [red]✗ URL refresh failed on retry {attempt}: {exc}[/]")
                    all_cdn_broken = False
                    last_exc = exc
                    continue
            progress.update(task, completed=0, total=None)

        try:
            with session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                dbg(f"  Content-Length: {total} bytes  (attempt {attempt + 1})")
                progress.update(task, total=total)
                dest.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=131072):
                        if chunk:
                            f.write(chunk)
                            written += len(chunk)
                            progress.advance(task, len(chunk))
            dbg(f"  Download complete — {written} bytes written")
            return True, False
        except requests.RequestException as exc:
            last_exc = exc
            if not _INCOMPLETE_READ_RE.search(str(exc)):
                all_cdn_broken = False
            dbg(f"  Network error on attempt {attempt + 1}: {exc}")
            if attempt == retries:
                console.print(
                    f"  [red]✗ Network error (all {retries + 1} attempt(s) failed): {exc}[/]"
                )
        except OSError as exc:
            console.print(f"  [red]✗ File write error: {exc}[/]")
            return False, False

    return False, all_cdn_broken


# ─────────────────────────────────────────────────────────────────────────────
# Duration check helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_audio_duration(path: Path) -> Optional[float]:
    """Return the audio duration of *path* in seconds, or None on failure.

    Uses mutagen (already a hard dependency) to inspect both FLAC and MP3 files
    without re-reading the entire file.
    """
    try:
        from mutagen import File as MutagenFile  # type: ignore
        audio = MutagenFile(path)
        if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length"):
            length = float(audio.info.length)
            dbg(f"  Duration check: {path.name} → {length:.1f}s")
            return length
    except Exception as exc:
        dbg(f"  Duration check failed ({path.name}): {exc}")
    return None


def _is_preview_duration(measured: float, expected_seconds: int) -> bool:
    """Return True if *measured* looks like a Qobuz 30-second preview clip.

    Two conditions must both hold:
      1. The measured duration is within PREVIEW_DURATION_TOLERANCE of
         PREVIEW_DURATION (30 s).
      2. The track's expected API duration is long enough that it *cannot*
         legitimately be a ~30 s track — this avoids false positives on
         genuinely short pieces.
    """
    near_preview = abs(measured - PREVIEW_DURATION) <= PREVIEW_DURATION_TOLERANCE
    track_is_longer = expected_seconds > PREVIEW_DURATION + PREVIEW_DURATION_TOLERANCE
    return near_preview and track_is_longer


# ─────────────────────────────────────────────────────────────────────────────
# Single-track download
# ─────────────────────────────────────────────────────────────────────────────

def download_single_track(
    api:              QobuzAPI,
    track:            Dict,
    out_dir:          Path,
    track_tmpl:       str,
    quality_id:       str,
    cover:            Optional[bytes],
    meta_fields:      Optional[Dict[str, bool]],
    skip_existing:    bool,
    progress:         Progress,
    cfg:              Optional[Dict[str, Any]] = None,
    total_tracks:     int = 1,
    retries:          int = 3,
    on_final_failure: str = "delete_partial",
    force_main_album_artist: bool = False,
    override_main_artist: Optional[str] = None,
) -> bool:
    """Download a single track, with optional quality fallback on CDN errors
    and optional duration-check to detect expired-token 30-second previews.

    Quality fallback
    ~~~~~~~~~~~~~~~~
    When ``cfg["quality_fallback"]`` is True and every retry fails with the
    ``IncompleteRead(1 bytes read, …)`` CDN pattern, the download is retried
    at the next lower quality in ``cfg["quality_fallback_path"]``.

    Duration check
    ~~~~~~~~~~~~~~
    When ``cfg["duration_check"]`` is True, the downloaded file's audio
    duration is measured with mutagen after each successful HTTP transfer.
    If the file is ~30 seconds long but the API reports a longer duration,
    Qobuz has served a preview clip — a sign the current auth token is
    expired.  qobuz-dl then retries the download using each remaining
    configured token in turn.  If all tokens produce previews, the failure
    is handled by ``on_final_failure`` exactly like a network failure.

    Returns True on success.
    """
    album     = track.get("album", {})
    trunc_cfg = cfg if cfg is not None else api.cfg
    title     = track.get("title", "Unknown")
    track_no  = track.get("track_number", 0)
    disc_no   = track.get("media_number", 1)
    pad       = len(str(total_tracks))
    label     = f"  [cyan]{track_no:>{pad}}.[/] {title[:55]}"

    duration_check = bool(cfg.get("duration_check", False)) if cfg else False
    expected_secs  = int(track.get("duration", 0))

    def _artist() -> str:
        return (
            get_artists(album) if album.get("artists")
            else track.get("performer", {}).get("name", "Various Artists")
        )

    def _filename(q_id: str) -> str:
        ext = EXT_MAP.get(q_id, "flac")
        raw = safe_format(
            track_tmpl,
            track    = track_no,
            disc     = disc_no,
            title    = title,
            artist   = _artist(),
            album    = album.get("title", ""),
            year     = get_year(album),
            track_id = str(track.get("id", "")),
        ) + f".{ext}"
        return truncate_name(clean_name(raw), trunc_cfg, "filename")

    # ── build the ordered list of quality IDs to attempt ─────────────────────
    qualities_to_try: List[str] = [quality_id]
    if cfg and cfg.get("quality_fallback", False):
        path_keys = cfg.get("quality_fallback_path", QUALITY_ORDER)
        path_ids  = [QUALITY_MAP[k] for k in path_keys if k in QUALITY_MAP]
        if quality_id in path_ids:
            idx = path_ids.index(quality_id)
            qualities_to_try = path_ids[idx:]   # requested quality + all fallbacks below it

    # ── attempt each quality in order ────────────────────────────────────────
    dest: Path = out_dir / _filename(quality_id)   # kept up-to-date each iteration

    for i, q_id in enumerate(qualities_to_try):
        is_fallback = i > 0
        fname = _filename(q_id)
        dest  = out_dir / fname
        ext   = EXT_MAP.get(q_id, "flac")
        dbg(
            f"Track {track_no} → {dest}  ({len(fname.encode())}B)"
            + (f"  [fallback: {QUALITY_LABELS.get(q_id, q_id)}]" if is_fallback else "")
        )

        if skip_existing and dest.exists():
            dbg("  Skipping — file already exists")
            console.print(f"  [dim]⟳[/] {fname}")
            return True

        if is_fallback:
            console.print(
                f"  [yellow]⚠ CDN error on all retries — trying "
                f"{QUALITY_LABELS.get(q_id, q_id)}[/]"
            )

        try:
            url = api.get_track_url(track["id"], q_id)
        except Exception as exc:
            console.print(f"  [red]✗ URL fetch failed for '{title}': {exc}[/]")
            return False

        task = progress.add_task(label, total=None)
        ok, cdn_broken = stream_download(
            url, dest, api.session, progress, task, retries=retries,
            url_fetcher=lambda _q=q_id: api.get_track_url(track["id"], _q),
        )
        progress.remove_task(task)

        if ok:
            # ── duration check ────────────────────────────────────────────────
            if duration_check:
                ok = _duration_check_and_retry(
                    api=api,
                    track=track,
                    dest=dest,
                    q_id=q_id,
                    label=label,
                    fname=fname,
                    expected_secs=expected_secs,
                    retries=retries,
                    progress=progress,
                    cfg=cfg,
                )
                if not ok:
                    # All tokens returned previews — fall through to on_final_failure.
                    break

            if ok:
                if meta_fields is not None:
                    if ext == "flac":
                        embed_flac_metadata(
                            dest, track, cover, meta_fields,
                            force_main_album_artist, override_main_artist,
                        )
                    elif ext == "mp3":
                        embed_mp3_metadata(
                            dest, track, cover, meta_fields,
                            force_main_album_artist, override_main_artist,
                        )
                suffix = (
                    f" [dim](fallback: {QUALITY_LABELS.get(q_id, q_id)})[/]"
                    if is_fallback else ""
                )
                console.print(f"  [green]✓[/] {fname}{suffix}")
                return True

        # ── this quality failed ───────────────────────────────────────────────
        has_next = i < len(qualities_to_try) - 1
        if cdn_broken and has_next:
            # Clean up the 1-byte partial and try the next quality.
            dest.unlink(missing_ok=True)
            dbg(f"  Deleted partial file before fallback: {dest}")
            continue

        if cdn_broken and not has_next:
            console.print(
                f"  [red]✗ CDN error on all retries at every fallback quality "
                f"for '{title}'.[/]"
            )
        elif not cdn_broken:
            dbg("  Non-CDN failure — not attempting quality fallback")

        break   # fall through to on_final_failure

    # ── on_final_failure ─────────────────────────────────────────────────────
    partial_exists = dest.exists()
    if on_final_failure == "keep_partial":
        if partial_exists:
            console.print(
                f"  [yellow]⚠ Keeping partial file (resume later):[/] {dest.name}"
            )
    elif on_final_failure == "delete_album":
        if partial_exists:
            dest.unlink(missing_ok=True)
    else:   # "delete_partial" (default)
        if partial_exists:
            dest.unlink(missing_ok=True)
            dbg(f"  Deleted partial file: {dest}")

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Duration-check token-rotation helper
# ─────────────────────────────────────────────────────────────────────────────

def _duration_check_and_retry(
    api:          QobuzAPI,
    track:        Dict,
    dest:         Path,
    q_id:         str,
    label:        str,
    fname:        str,
    expected_secs: int,
    retries:      int,
    progress:     Progress,
    cfg:          Optional[Dict[str, Any]],
) -> bool:
    """Check whether *dest* is a 30-second preview; if so, retry with other tokens.

    Returns True if the file on disk is (or becomes) a full-length download.
    Returns False if every configured token produces a preview, leaving *dest*
    containing the last preview attempt (caller applies on_final_failure).
    """
    measured = _get_audio_duration(dest)

    if measured is None:
        # Can't measure — assume it's fine rather than false-positive aborting.
        dbg("  Duration check: unable to measure — skipping check")
        return True

    if not _is_preview_duration(measured, expected_secs):
        dbg(
            f"  Duration check passed: {measured:.1f}s  "
            f"(expected ≈{expected_secs}s)"
        )
        return True

    # ── preview detected ──────────────────────────────────────────────────────
    console.print(
        f"  [bold yellow]⚠ Preview detected[/] for [italic]{track.get('title', '?')}[/]: "
        f"file is {measured:.0f}s but track should be {expected_secs}s. "
        f"Auth token may be expired."
    )

    all_tokens = api.all_tokens
    dbg(f"  Will try {len(all_tokens)} token(s) to get the full file")

    for token_idx, token in enumerate(all_tokens):
        console.print(
            f"  [dim]Retrying with token {token_idx + 1}/{len(all_tokens)} "
            f"({token[:6]}…)[/]"
        )
        try:
            retry_url = api.get_track_url_with_token(track["id"], q_id, token)
        except Exception as exc:
            console.print(f"  [red]✗ URL fetch failed with token {token_idx + 1}: {exc}[/]")
            continue

        task = progress.add_task(label, total=None)
        ok, _cdn = stream_download(
            retry_url,
            dest,
            api.session,
            progress,
            task,
            retries=retries,
            url_fetcher=lambda _tok=token, _q=q_id: api.get_track_url_with_token(
                track["id"], _q, _tok
            ),
        )
        progress.remove_task(task)

        if not ok:
            dbg(f"  Token {token_idx + 1} — stream failed, trying next")
            continue

        retry_measured = _get_audio_duration(dest)
        if retry_measured is None:
            dbg(f"  Token {token_idx + 1} — duration unmeasurable, assuming success")
            return True

        if not _is_preview_duration(retry_measured, expected_secs):
            dbg(
                f"  Token {token_idx + 1} — full file confirmed "
                f"({retry_measured:.1f}s)"
            )
            return True

        dbg(
            f"  Token {token_idx + 1} — still a preview "
            f"({retry_measured:.0f}s), trying next"
        )

    # Every token produced a preview.
    console.print(
        f"  [bold red]✗ All {len(all_tokens)} token(s) returned a 30-second preview "
        f"for '{track.get('title', '?')}'. "
        f"Your auth token(s) may have expired — run [bold]qobuz-dl setup[/bold] "
        f"to update them.[/]"
    )
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dry_run_track_rows(
    tracks: List[Dict],
    out_dir: Path,
    track_tmpl: str,
    quality_id: str,
    skip_existing: bool,
    is_multidisc: bool,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Tuple[str, str, str]], int, int]:
    """Return (rows, would_download, already_exist) for a list of tracks.

    Each row is a tuple of (track_label, dest_path_str, action_markup).
    """
    rows: List[Tuple[str, str, str]] = []
    would_download = 0
    already_exist  = 0
    ext       = EXT_MAP.get(quality_id, "flac")
    trunc_cfg = cfg or {}

    for track in tracks:
        album    = track.get("album", {})
        track_no = track.get("track_number", 0)
        disc_no  = track.get("media_number", 1)
        title    = track.get("title", "Unknown")

        filename = safe_format(
            track_tmpl,
            track    = track_no,
            disc     = disc_no,
            title    = title,
            artist   = (
                get_artists(album) if album.get("artists") else
                track.get("performer", {}).get("name", "Various Artists")
            ),
            album    = album.get("title", ""),
            year     = get_year(album),
            track_id = str(track.get("id", "")),
        ) + f".{ext}"
        filename = truncate_name(clean_name(filename), trunc_cfg, "filename")

        if is_multidisc:
            dest = out_dir / f"Disc {disc_no}" / filename
        else:
            dest = out_dir / filename

        if dest.exists():
            already_exist += 1
            if skip_existing:
                action = "[dim]skip[/]"
            else:
                action = "[yellow]overwrite[/]"
                would_download += 1
        else:
            action = "[green]download[/]"
            would_download += 1

        rows.append((f"{track_no:>3}. {title[:50]}", str(dest), action))

    return rows, would_download, already_exist


def dry_run_album(
    api:          QobuzAPI,
    album_id:     str,
    cfg:          Dict[str, Any],
    quality_id:   str,
    root_dir:     Path,
    folder_tmpl:  str,
    track_tmpl:   str,
    override_main_artist: Optional[str] = None,
    global_artist_id: Optional[str] = None,
    auto_override_id: bool = False,
) -> Optional[str]:
    """Print a dry-run preview table for one album. Returns the artist_id string."""
    with console.status("Fetching album info…"):
        try:
            album = api.get_album(album_id)
        except Exception as exc:
            console.print(f"[red]✗ Could not fetch album {album_id}: {exc}[/]")
            return global_artist_id

    artist      = get_artists(album)
    main_artist = override_main_artist or get_main_artist(album)
    title       = album.get("title", "Unknown Album")
    year        = get_year(album)
    genre       = album.get("genre", {}).get("name", "")
    label       = album.get("label", {}).get("name", "")
    quality     = get_quality_tag(album)
    tracks      = album.get("tracks", {}).get("items", [])

    actual_artist_id = str(album.get("artist", {}).get("id", ""))
    artist_id_val    = (global_artist_id or actual_artist_id) if auto_override_id else actual_artist_id
    album_id_val     = str(album.get("id", album_id))

    for t in tracks:
        t["album"] = album

    if cfg.get("include_version", False):
        apply_version_to_title(album)
        for t in tracks:
            apply_version_to_title(t)
    if cfg.get("strip_feat_from_album_title", False):
        strip_feat_from_album_title(album)
    if cfg.get("strip_feat_from_track_title", False):
        for t in tracks:
            strip_feat_from_track_title(t)

    folder_name = truncate_name(safe_format(
        folder_tmpl,
        artist      = artist,
        main_artist = main_artist,
        album       = album.get("title", "Unknown Album"),
        year        = year,
        genre       = genre,
        label       = label,
        quality     = quality,
        artist_id   = artist_id_val,
        album_id    = album_id_val,
    ), cfg, "folder")
    out_dir = root_dir / folder_name

    disc_nos     = sorted({t.get("media_number", 1) for t in tracks})
    is_multidisc = len(disc_nos) > 1 and cfg.get("multi_disc", True)
    skip_existing = cfg.get("skip_existing", True)

    rows, would_download, already_exist = _dry_run_track_rows(
        tracks, out_dir, track_tmpl, quality_id, skip_existing, is_multidisc, cfg
    )

    console.print(
        Panel(
            f"[bold]{artist}[/] — [italic]{title}[/]  [dim]({year})[/]\n"
            f"[dim]Folder:[/] {out_dir}\n"
            f"{len(tracks)} track(s)  ·  {quality}  ·  "
            f"[green]{would_download} to download[/]  ·  [dim]{already_exist} already exist[/]",
            title="[bold blue]Dry Run — Album[/]",
            border_style="blue",
        )
    )

    t = Table(border_style="dim", show_lines=False, show_header=True)
    t.add_column("Track",  max_width=55)
    t.add_column("Action", justify="center", no_wrap=True)
    for track_label, _dest, action in rows:
        t.add_row(track_label, action)
    console.print(t)

    return artist_id_val


# ─────────────────────────────────────────────────────────────────────────────
# Album orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def download_album(
    api:           QobuzAPI,
    album_id:      str,
    cfg:           Dict[str, Any],
    quality_id:    str,
    root_dir:      Path,
    folder_tmpl:   str,
    track_tmpl:    str,
    override_main_artist: Optional[str] = None,
    force_artist_id: Optional[str] = None,
    auto_override_id: bool = False,
) -> Optional[str]:
    with console.status("Fetching album info…"):
        try:
            album = api.get_album(album_id)
        except Exception as exc:
            console.print(f"[red]✗ Could not fetch album {album_id}: {exc}[/]")
            return force_artist_id

    artist      = get_artists(album)
    main_artist = override_main_artist or get_main_artist(album)
    title       = album.get("title", "Unknown Album")
    year        = get_year(album)
    genre       = album.get("genre", {}).get("name", "")
    label       = album.get("label", {}).get("name", "")
    quality     = get_quality_tag(album)
    tracks      = album.get("tracks", {}).get("items", [])

    actual_artist_id = str(album.get("artist", {}).get("id", ""))
    artist_id_val    = (force_artist_id or actual_artist_id) if auto_override_id else actual_artist_id
    album_id_val     = str(album.get("id", album_id))

    for t in tracks:
        t["album"] = album

    if cfg.get("include_version", False):
        apply_version_to_title(album)
        for t in tracks:
            apply_version_to_title(t)
    if cfg.get("strip_feat_from_album_title", False):
        strip_feat_from_album_title(album)
    if cfg.get("strip_feat_from_track_title", False):
        for t in tracks:
            strip_feat_from_track_title(t)

    folder_name = truncate_name(safe_format(
        folder_tmpl,
        artist      = artist,
        main_artist = main_artist,
        album       = album.get("title", "Unknown Album"),
        year        = year,
        genre       = genre,
        label       = label,
        quality     = quality,
        artist_id   = artist_id_val,
        album_id    = album_id_val,
    ), cfg, "folder")
    out_dir = root_dir / folder_name
    dbg(f"Album output dir → {out_dir}  ({len(folder_name.encode())}B)")

    disc_nos     = sorted({t.get("media_number", 1) for t in tracks})
    is_multidisc = len(disc_nos) > 1 and cfg.get("multi_disc", True)
    dbg(f"Disc(s): {disc_nos}  multi_disc={is_multidisc}  tracks={len(tracks)}")

    console.print(
        Panel(
            f"[bold]{artist}[/] — [italic]{title}[/]  [dim]({year})[/]\n"
            f"{genre}  ·  {len(tracks)} track(s)  ·  {quality}",
            title="[bold blue]Downloading Album[/]",
            border_style="blue",
        )
    )

    meta_flds           = get_meta_fields(cfg)
    embed_cover_in_file = meta_flds is not None and meta_flds.get("cover", True)

    cover_size       = cfg.get("cover_size", "original")
    embed_cover_size = cfg.get("embed_cover_size", "original")
    oversize_action  = cfg.get("embed_cover_oversize_action", "use_large")

    cover_for_save:  Optional[bytes] = None
    cover_for_embed: Optional[bytes] = None

    need_save  = bool(cfg.get("save_cover"))
    need_embed = embed_cover_in_file

    if need_save or need_embed:
        with console.status("Fetching cover art…"):
            if need_save and need_embed and cover_size == embed_cover_size:
                # Both purposes need the same size — fetch once, reuse.
                data = fetch_cover_for_embed(album, api.session, embed_cover_size, oversize_action)
                cover_for_save  = data
                cover_for_embed = data
            else:
                if need_save:
                    cover_for_save = fetch_cover(album, api.session, cover_size)
                if need_embed:
                    cover_for_embed = fetch_cover_for_embed(
                        album, api.session, embed_cover_size, oversize_action
                    )

    if need_save and cover_for_save:
        cover_path = out_dir / "cover.jpg"
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        if not cover_path.exists():
            cover_path.write_bytes(cover_for_save)
            console.print("  [green]✓[/] cover.jpg")

    retries          = int(cfg.get("retries", 3))
    on_final_failure = cfg.get("on_final_failure", "delete_partial")

    downloaded_files: List[Path] = []
    if need_save and cover_for_save:
        downloaded_files.append(out_dir / "cover.jpg")

    abort_album = False

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        for track in tracks:
            if not track.get("streamable", True):
                console.print(f"  [yellow]⊘ Not streamable:[/] {track.get('title', '?')}")
                continue

            disc = track.get("media_number", 1)
            track_dir = out_dir / f"Disc {disc}" if is_multidisc else out_dir

            ok = download_single_track(
                api              = api,
                track            = track,
                out_dir          = track_dir,
                track_tmpl       = track_tmpl,
                quality_id       = quality_id,
                cover            = cover_for_embed,
                meta_fields      = meta_flds,
                skip_existing    = cfg.get("skip_existing", True),
                progress         = progress,
                cfg              = cfg,
                total_tracks     = len(tracks),
                retries          = retries,
                on_final_failure = on_final_failure,
                force_main_album_artist = cfg.get("force_main_album_artist", False),
                override_main_artist    = override_main_artist,
            )

            if ok:
                ext      = EXT_MAP.get(quality_id, "flac")
                filename = truncate_name(clean_name(
                    safe_format(
                        track_tmpl,
                        track    = track.get("track_number", 0),
                        disc     = track.get("media_number", 1),
                        title    = track.get("title", "Unknown"),
                        artist   = (
                            get_artists(album) if album.get("artists") else
                            track.get("performer", {}).get("name", "Various Artists")
                        ),
                        album    = album.get("title", ""),
                        year     = get_year(album),
                        track_id = str(track.get("id", "")),
                    ) + f".{ext}"
                ), cfg, "filename")
                downloaded_files.append(track_dir / filename)
            elif on_final_failure == "delete_album":
                abort_album = True
                break

    if abort_album:
        console.print(
            f"  [red bold]⚠ Track failed — deleting all {len(downloaded_files)} "
            f"downloaded file(s) for this album.[/]"
        )
        for f in downloaded_files:
            try:
                f.unlink(missing_ok=True)
                dbg(f"  Deleted: {f}")
            except OSError as exc:
                dbg(f"  Could not delete {f}: {exc}")
        for d in sorted(out_dir.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass
        try:
            out_dir.rmdir()
        except OSError:
            pass
        console.print(f"  [dim]Album folder cleaned up: {out_dir}[/]")
    else:
        console.print(f"\n[bold green]✓ Done![/]  →  {out_dir}\n")

    return artist_id_val
