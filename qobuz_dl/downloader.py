"""
downloader.py — Download pipeline: HTTP streaming, single-track download,
dry-run preview, and full album orchestration.
"""

from __future__ import annotations

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
from .constants import EXT_MAP
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
) -> bool:
    """Stream *url* to *dest*, retrying up to *retries* times with exponential back-off.

    Returns True on success.  The partial file (if any) is left in place on
    failure so the caller can decide what to do with it.
    """
    dbg(f"Streaming download → {dest}  (retries={retries})")
    dbg(f"  URL: {url}")
    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        if attempt > 0:
            delay = 2 ** attempt
            dbg(f"  Retry {attempt}/{retries} — waiting {delay}s after: {last_exc}")
            console.print(f"  [yellow]⟳ Retry {attempt}/{retries}[/] — waiting {delay}s…")
            time.sleep(delay)
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
            return True
        except requests.RequestException as exc:
            last_exc = exc
            dbg(f"  Network error on attempt {attempt + 1}: {exc}")
            if attempt == retries:
                console.print(
                    f"  [red]✗ Network error (all {retries + 1} attempt(s) failed): {exc}[/]"
                )
        except OSError as exc:
            console.print(f"  [red]✗ File write error: {exc}[/]")
            return False

    return False


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
    """Download a single track, honouring retry and on-failure settings.

    Returns True on success.

    on_final_failure controls what happens to the partial file after all
    retry attempts are exhausted:
      "keep_partial"   — leave the partial file on disk (resume-friendly)
      "delete_partial" — delete just the partial file and continue
      "delete_album"   — signal the album orchestrator to wipe all album files
    """
    album     = track.get("album", {})
    ext       = EXT_MAP.get(quality_id, "flac")
    track_no  = track.get("track_number", 0)
    disc_no   = track.get("media_number", 1)
    title     = track.get("title", "Unknown")
    trunc_cfg = cfg if cfg is not None else api.cfg

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
    dest     = out_dir / filename
    dbg(f"Track {track_no} → {dest}  ({len(filename.encode())}B)")

    if skip_existing and dest.exists():
        dbg("  Skipping — file already exists")
        console.print(f"  [dim]⟳[/] {filename}")
        return True

    try:
        url = api.get_track_url(track["id"], quality_id)
    except Exception as exc:
        console.print(f"  [red]✗ URL fetch failed for '{title}': {exc}[/]")
        return False

    pad   = len(str(total_tracks))
    label = f"  [cyan]{track_no:>{pad}}.[/] {title[:55]}"
    task  = progress.add_task(label, total=None)
    ok    = stream_download(url, dest, api.session, progress, task, retries=retries)
    progress.remove_task(task)

    if ok:
        if meta_fields is not None:
            if ext == "flac":
                embed_flac_metadata(dest, track, cover, meta_fields, force_main_album_artist, override_main_artist)
            elif ext == "mp3":
                embed_mp3_metadata(dest, track, cover, meta_fields, force_main_album_artist, override_main_artist)
        console.print(f"  [green]✓[/] {filename}")
    else:
        partial_exists = dest.exists()
        if on_final_failure == "keep_partial":
            if partial_exists:
                console.print(f"  [yellow]⚠ Keeping partial file (resume later):[/] {filename}")
        elif on_final_failure == "delete_album":
            if partial_exists:
                dest.unlink(missing_ok=True)
        else:
            # "delete_partial" (default)
            if partial_exists:
                dest.unlink(missing_ok=True)
                dbg(f"  Deleted partial file: {dest}")

    return ok


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
