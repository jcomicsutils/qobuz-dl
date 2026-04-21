#!/usr/bin/env python3
"""
qobuz-dl — A feature-rich command-line Qobuz downloader
Downloads music via the official Qobuz API.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import requests
from rich.console import Console
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

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Verbose / debug helpers
# ─────────────────────────────────────────────────────────────────────────────

# Module-level flag — set to True by the --verbose CLI option before any
# subcommand runs.  All code can call dbg() without passing state around.
_VERBOSE: bool = False


def dbg(msg: str) -> None:
    """Print a debug line when --verbose is active.  Silently a no-op otherwise."""
    if _VERBOSE:
        console.print(f"[dim][DEBUG][/dim] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Constants & defaults
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".config" / "qobuz-dl"
CONFIG_FILE = CONFIG_DIR / "config.json"

ALBUM_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/album/([a-zA-Z0-9]+)")
TRACK_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/track/(\d+)")
ARTIST_URL_RE = re.compile(r"https?://(?:play|open)\.qobuz\.com/artist/(\d+)")

QUALITY_MAP: Dict[str, str] = {
    "mp3":        "5",
    "cd":         "6",
    "hi-res":     "7",
    "hi-res-192": "27",
}

QUALITY_LABELS: Dict[str, str] = {
    "5":  "MP3 320 kbps",
    "6":  "FLAC 16-bit / 44.1 kHz  (CD)",
    "7":  "FLAC 24-bit / up to 96 kHz",
    "27": "FLAC 24-bit / up to 192 kHz",
}

EXT_MAP: Dict[str, str] = {
    "5":  "mp3",
    "6":  "flac",
    "7":  "flac",
    "27": "flac",
}

ILLEGAL_CHARS = r'/\?:*"<>|'

# Canonical metadata field names and their defaults.
# Each key maps to a single tag in both FLAC (Vorbis comments) and MP3 (ID3).
# "cover" controls embedded album art inside the audio file (separate from cover.jpg).
METADATA_FIELDS: Dict[str, bool] = {
    "title":        True,
    "artist":       True,
    "album_artist": True,
    "album":        True,
    "track_number": True,
    "disc_number":  True,
    "date":         True,
    "year":         True,
    "genre":        True,
    "label":        True,
    "copyright":    True,
    "isrc":         True,
    "upc":          True,
    "cover":        True,   # embedded cover art inside the audio file
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_id":          "",
    "auth_tokens":     [],
    "secret":          "",
    "api_base":        "https://www.qobuz.com/api.json/0.2/",
    "download_dir":    str(Path.home() / "Music" / "Qobuz"),
    "quality":         "hi-res-192",
    "folder_template": "{artist}/{album} ({year}) [{quality}]",
    "track_template":  "{track:02d} - {title}",
    "multi_disc":      True,
    "save_cover":      True,
    "embed_metadata":  True,
    "metadata_fields": dict(METADATA_FIELDS),
    "skip_existing":   True,
    "socks5_proxy":    "",
    "include_version": True,
    "force_main_album_artist": False,
    "strip_feat_from_album_title": False,
    "strip_feat_from_track_title": False,
}

TEMPLATE_HELP = """
\b
Template variables
──────────────────
  Folder:  {artist}     {album}    {year}     {genre}  {label}  {quality}
           {artist_id}  {album_id}
  Track:   {track}      {disc}     {title}    {artist} {album}  {year}
           {track_id}

Use Python format specs — e.g. {track:02d} for zero-padded track numbers.
Include {album_id} / {artist_id} / {track_id} to avoid collisions when two
releases share the same name.

Examples
─────────
  Folder template:  {main_artist}/{album} ({year}) [{album_id}]
  Track  template:  {track:02d} - {title} [{track_id}]
"""


# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────


def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        dbg(f"Loading config from {CONFIG_FILE}")
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        dbg(f"Config loaded — quality={cfg.get('quality')!r}  download_dir={cfg.get('download_dir')!r}")
        return cfg
    dbg("No config file found — using built-in defaults")
    return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)



def get_meta_fields(cfg: Dict[str, Any]) -> Optional[Dict[str, bool]]:
    """Return the resolved per-field metadata gates, or None if embedding is disabled.

    Merges METADATA_FIELDS defaults with whatever is stored in cfg so that
    fields added in future versions are enabled by default for existing configs.
    """
    if not cfg.get("embed_metadata", True):
        return None
    resolved = dict(METADATA_FIELDS)                  # start from canonical defaults
    resolved.update(cfg.get("metadata_fields", {}))   # overlay user prefs
    return resolved


# ─────────────────────────────────────────────────────────────────────────────
# Qobuz API
# ─────────────────────────────────────────────────────────────────────────────


class QobuzAPI:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg     = cfg
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "qobuz-dl/1.0"})
        if cfg.get("socks5_proxy"):
            proxy = f"socks5://{cfg['socks5_proxy']}"
            self.session.proxies = {"http": proxy, "https": proxy}

    # ── authentication ────────────────────────────────────────────────────────

    @property
    def token(self) -> str:
        tokens = self.cfg.get("auth_tokens", [])
        if not tokens:
            raise click.ClickException(
                "No auth tokens configured. Run [bold]qobuz-dl setup[/bold]."
            )
        return random.choice(tokens)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-app-id":          self.cfg["app_id"],
            "x-user-auth-token": self.token,
        }

    # ── request ───────────────────────────────────────────────────────────────

    def _get(self, endpoint: str, **params: Any) -> Any:
        base = self.cfg.get("api_base", DEFAULT_CONFIG["api_base"]).rstrip("/")
        url  = f"{base}/{endpoint.lstrip('/')}"
        # Mask the auth token in debug output so logs are safe to share
        safe_params = {k: ("***" if k == "request_sig" else v) for k, v in params.items()}
        dbg(f"GET {url}  params={safe_params}")
        r    = self.session.get(url, headers=self._headers(), params=params, timeout=30)
        dbg(f"→ HTTP {r.status_code}  ({len(r.content)} bytes)")
        r.raise_for_status()
        return r.json()

    # ── endpoints ─────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10, offset: int = 0) -> Dict:
        return self._get("catalog/search", query=query, limit=limit, offset=offset)

    def get_album(self, album_id: str) -> Dict:
        return self._get("album/get", album_id=album_id, extra="track_ids")

    def get_track(self, track_id: str) -> Dict:
        return self._get("track/get", track_id=track_id)

    def get_artist(self, artist_id: str) -> Dict:
        return self._get("artist/page", artist_id=artist_id, sort="release_date")

    def get_artist_releases(
        self,
        artist_id: str,
        release_type: str = "album",
        limit: int = 500,
        offset: int = 0,
    ) -> Dict:
        return self._get(
            "artist/getReleasesList",
            artist_id=artist_id,
            release_type=release_type,
            limit=limit,
            offset=offset,
            sort="release_date",
            track_size=1000,
        )

    def get_track_url(self, track_id: int, quality: str) -> str:
        secret  = self.cfg["secret"]
        ts      = int(time.time())
        r_sig   = (
            f"trackgetFileUrlformat_id{quality}"
            f"intentstreamtrack_id{track_id}{ts}{secret}"
        )
        sig_md5 = hashlib.md5(r_sig.encode()).hexdigest()
        dbg(f"Requesting file URL — track_id={track_id}  format_id={quality}  ts={ts}")
        data    = self._get(
            "track/getFileUrl",
            format_id=quality,
            intent="stream",
            track_id=track_id,
            request_ts=ts,
            request_sig=sig_md5,
        )
        dbg(f"File URL obtained — mime={data.get('mime_type')!r}  "
            f"sampling_rate={data.get('sampling_rate')}  bit_depth={data.get('bit_depth')}")
        return data["url"]


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


def clean_name(name: str) -> str:
    """Strip filesystem-illegal characters from a name segment."""
    for ch in ILLEGAL_CHARS:
        name = name.replace(ch, "_")
    return name.strip(". ")


def safe_format(template: str, **kwargs: Any) -> str:
    """Apply a template, sanitising every string value."""
    safe: Dict[str, Any] = {}
    for k, v in kwargs.items():
        safe[k] = clean_name(str(v)) if isinstance(v, str) else v
    try:
        return template.format_map(safe)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(f"Template error: {exc}") from exc


def get_artists(album: Dict) -> str:
    artists = album.get("artists") or []
    if artists:
        return ", ".join(a["name"] for a in artists)
    return album.get("artist", {}).get("name", "Various Artists")

def get_main_artist(album: Dict) -> str:
    """Return only the primary artist of the album."""
    return album.get("artist", {}).get("name", "Unknown Artist")


def get_year(album: Dict) -> str:
    date = album.get("release_date_original", "")
    return date[:4] if date else "????"


def get_quality_tag(album: Dict) -> str:
    bits = album.get("maximum_bit_depth", 0)
    rate = album.get("maximum_sampling_rate", 0)
    if bits and rate:
        return f"FLAC {bits}bit {int(rate)}kHz"
    return "FLAC"


def resolve_url(token: str) -> Tuple[str, str]:
    """Return (kind, id) from a Qobuz URL."""
    m = ALBUM_URL_RE.search(token)
    if m:
        return "album", m.group(1)
    m = TRACK_URL_RE.search(token)
    if m:
        return "track", m.group(1)
    m = ARTIST_URL_RE.search(token)
    if m:
        return "artist", m.group(1)
    raise click.ClickException(
        f"Unrecognised URL: {token!r}\n"
        "  Only Qobuz URLs (https://play.qobuz.com/…) are accepted here."
    )


_ID_PREFIXES: Dict[str, str] = {
    "ar-id": "artist",
    "al-id": "album",
    "tr-id": "track",
}


def parse_targets(tokens: Tuple[str, ...]) -> List[Tuple[str, str]]:
    """Convert a flat CLI token list into (kind, id) pairs.

    Every token must be either a full Qobuz URL or preceded by a type prefix.
    Bare IDs without a prefix are rejected with a descriptive error.

        ar-id 707261 4698030  → [("artist", "707261"), ("artist", "4698030")]
        al-id 0060253780948   → [("album",  "0060253780948")]
        tr-id 23929921        → [("track",  "23929921")]
        https://play.qobuz.com/album/xyz  → [("album", "xyz")]
        123456                → ClickException (bare ID, no prefix)
    """
    targets: List[Tuple[str, str]] = []
    i = 0
    current_prefix = None

    while i < len(tokens):
        tok = tokens[i].strip()

        # If it's a known prefix, update the active prefix state
        if tok in _ID_PREFIXES:
            current_prefix = _ID_PREFIXES[tok]
            i += 1
            if i >= len(tokens):
                raise click.ClickException(
                    f"'{tok}' must be followed by at least one ID."
                )
            continue

        # If it's a URL, clear the active prefix and resolve normally
        if tok.startswith("http://") or tok.startswith("https://"):
            current_prefix = None
            targets.append(resolve_url(tok))
        else:
            # Apply the active prefix if there is one; bare IDs without a
            # prefix are rejected — the type would be ambiguous otherwise.
            if current_prefix:
                targets.append((current_prefix, tok))
            else:
                raise click.ClickException(
                    f"Bare ID {tok!r} has no type prefix.\n"
                    "  Use one of the key prefixes before your ID:\n"
                    "    ar-id <id>   — artist\n"
                    "    al-id <id>   — album\n"
                    "    tr-id <id>   — track\n"
                    "  Or pass a full Qobuz URL (https://play.qobuz.com/…)."
                )

        i += 1

    return targets


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"

def apply_version_to_title(data: Dict) -> None:
    """Appends the 'version' (edition) to the 'title' if present."""
    version = data.get("version")
    if version and version.strip():
        title = data.get("title", "")
        if f"({version})" not in title:
            data["title"] = f"{title} ({version.strip()})"


# Matches "(feat. ...)", "[ft. ...]", "{featuring ...}" etc. at the end of a title —
# case-insensitive, anchored to $ so it won't fire mid-title.
_FEAT_RE = re.compile(
    r"(?i)\s*[(\[{]\s*(?:feat\.?|ft\.?|featuring|featured)\s+([^()\[\]{}]+)[)\]}]\s*$"
)


def _track_has_featured_artist(track: Dict) -> bool:
    """Return True if Qobuz's performers string explicitly lists a FeaturedArtist role.
    This field is only present on track objects, not album objects."""
    performers = track.get("performers", "")
    return bool(performers) and "FeaturedArtist" in performers


def strip_feat_from_track_title(track: Dict) -> None:
    """Remove '(feat. ...)' from a track's title, gated on Qobuz's performers
    field confirming a featured artist is present. In-place."""
    if not _track_has_featured_artist(track):
        return
    track["title"] = _FEAT_RE.sub("", track.get("title", "")).strip()


def strip_feat_from_album_title(album: Dict) -> None:
    """Remove '(feat. ...)' from an album's title. Albums have no performers field,
    so we rely on the regex alone — the user has already opted in via config."""
    album["title"] = _FEAT_RE.sub("", album.get("title", "")).strip()

# ─────────────────────────────────────────────────────────────────────────────
# Cover art
# ─────────────────────────────────────────────────────────────────────────────


def fetch_cover(album: Dict, session: requests.Session) -> Optional[bytes]:
    img_url = album.get("image", {}).get("large", "")
    if img_url:
        # Replace last 7 chars (e.g. "600.jpg") with "org.jpg" for full-res
        img_url = img_url[:-7] + "org.jpg"
    if not img_url:
        dbg("No cover image URL found in album data")
        return None
    dbg(f"Fetching cover art from {img_url}")
    try:
        r = session.get(img_url, timeout=20)
        r.raise_for_status()
        dbg(f"Cover art fetched — {len(r.content)} bytes")
        return r.content
    except Exception as exc:
        dbg(f"Cover art fetch failed: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Metadata embedding
# ─────────────────────────────────────────────────────────────────────────────


def embed_flac_metadata(
    path: Path, track: Dict, cover: Optional[bytes], fields: Dict[str, bool], force_main_album_artist: bool = False, override_main_artist: Optional[str] = None
) -> None:
    """Write Vorbis comment tags to a FLAC file, respecting per-field gates."""
    f = fields  # shorthand
    dbg(f"Embedding FLAC metadata → {path.name}  enabled_fields={[k for k,v in f.items() if v]}")
    try:
        from mutagen.flac import FLAC, Picture  # type: ignore

        audio = FLAC(path)
        album = track.get("album", {})
        artist = (
            get_artists(album) if album.get("artists") else
            track.get("performer", {}).get("name", "")
        )

        album_artist_val = override_main_artist or (get_main_artist(album) if force_main_album_artist else get_artists(album))

        if f.get("title"):        audio["title"]       = track.get("title", "")
        if f.get("track_number"): audio["tracknumber"] = str(track.get("track_number", ""))
        if f.get("disc_number"):  audio["discnumber"]  = str(track.get("media_number", "1"))
        if f.get("artist"):       audio["artist"]      = artist
        if f.get("album_artist"): audio["albumartist"] = album_artist_val
        if f.get("album"):        audio["album"]       = album.get("title", "")
        if f.get("date"):
            audio["date"] = album.get("release_date_original", "")
        elif f.get("year"):
            audio["date"] = get_year(album)
        if f.get("genre"):        audio["genre"]       = album.get("genre", {}).get("name", "")
        if f.get("label"):        audio["label"]       = album.get("label", {}).get("name", "")
        if f.get("copyright"):    audio["copyright"]   = track.get("copyright", "")
        if f.get("isrc") and track.get("isrc"):
            audio["isrc"] = track["isrc"]
        if f.get("upc") and album.get("upc"):
            audio["barcode"] = album["upc"]
        if f.get("cover") and cover:
            pic      = Picture()
            pic.type = 3         # Front cover
            pic.mime = "image/jpeg"
            pic.data = cover
            audio.add_picture(pic)
        audio.save()
    except ImportError:
        console.print("  [yellow]⚠ mutagen not installed — skipping metadata[/]")
    except Exception as exc:
        console.print(f"  [yellow]⚠ FLAC metadata error: {exc}[/]")


def embed_mp3_metadata(
    path: Path, track: Dict, cover: Optional[bytes], fields: Dict[str, bool], force_main_album_artist: bool = False, override_main_artist: Optional[str] = None
) -> None:
    """Write ID3 tags to an MP3 file, respecting per-field gates."""
    f = fields  # shorthand
    dbg(f"Embedding MP3/ID3 metadata → {path.name}  enabled_fields={[k for k,v in f.items() if v]}")
    try:
        from mutagen.id3 import (  # type: ignore
            APIC, ID3, TALB, TCOP, TCON, TDRC, TIT2, TPE1, TPE2, TPOS,
            TPUB, TRCK, TSRC,
        )
        from mutagen.mp3 import MP3  # type: ignore

        audio = MP3(path)
        if audio.tags is None:
            audio.add_tags()
        tags  = audio.tags
        album = track.get("album", {})

        artist = (
            get_artists(album) if album.get("artists") else
            track.get("performer", {}).get("name", "")
        )

        album_artist_val = override_main_artist or (get_main_artist(album) if force_main_album_artist else get_artists(album))

        if f.get("title"):        tags.add(TIT2(encoding=3, text=track.get("title", "")))
        if f.get("artist"):       tags.add(TPE1(encoding=3, text=artist))
        if f.get("album_artist"): tags.add(TPE2(encoding=3, text=album_artist_val))
        if f.get("album"):        tags.add(TALB(encoding=3, text=album.get("title", "")))
        if f.get("track_number"): tags.add(TRCK(encoding=3, text=str(track.get("track_number", ""))))
        if f.get("disc_number"):  tags.add(TPOS(encoding=3, text=str(track.get("media_number", "1"))))
        if f.get("date"):         tags.add(TDRC(encoding=3, text=album.get("release_date_original", "")))
        if f.get("genre"):        tags.add(TCON(encoding=3, text=album.get("genre", {}).get("name", "")))
        if f.get("label"):        tags.add(TPUB(encoding=3, text=album.get("label", {}).get("name", "")))
        if f.get("copyright"):    tags.add(TCOP(encoding=3, text=track.get("copyright", "")))
        if f.get("isrc") and track.get("isrc"):
            tags.add(TSRC(encoding=3, text=track["isrc"]))
        if f.get("cover") and cover:
            tags.add(
                APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover)
            )
        audio.save()
    except ImportError:
        console.print("  [yellow]⚠ mutagen not installed — skipping metadata[/]")
    except Exception as exc:
        console.print(f"  [yellow]⚠ MP3 metadata error: {exc}[/]")


# ─────────────────────────────────────────────────────────────────────────────
# Download primitives
# ─────────────────────────────────────────────────────────────────────────────


def stream_download(
    url: str,
    dest: Path,
    session: requests.Session,
    progress: Progress,
    task: TaskID,
) -> bool:
    dbg(f"Streaming download → {dest}")
    dbg(f"  URL: {url}")
    try:
        with session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            dbg(f"  Content-Length: {total} bytes")
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
        console.print(f"  [red]✗ Network error: {exc}[/]")
        return False
    except OSError as exc:
        console.print(f"  [red]✗ File write error: {exc}[/]")
        return False


def download_single_track(
    api:           QobuzAPI,
    track:         Dict,
    out_dir:       Path,
    track_tmpl:    str,
    quality_id:    str,
    cover:         Optional[bytes],
    meta_fields:   Optional[Dict[str, bool]],
    skip_existing: bool,
    progress:      Progress,
    total_tracks:  int = 1,
    force_main_album_artist: bool = False,
    override_main_artist: Optional[str] = None
) -> bool:
    album    = track.get("album", {})
    ext      = EXT_MAP.get(quality_id, "flac")
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
    filename = clean_name(filename)
    dest     = out_dir / filename
    dbg(f"Track {track_no} → {dest}")

    if skip_existing and dest.exists():
        dbg(f"  Skipping — file already exists")
        console.print(f"  [dim]⟳[/] {filename}")
        return True

    try:
        url = api.get_track_url(track["id"], quality_id)
    except Exception as exc:
        console.print(f"  [red]✗ URL fetch failed for '{title}': {exc}[/]")
        return False

    pad = len(str(total_tracks))
    label = f"  [cyan]{track_no:>{pad}}.[/] {title[:55]}"
    task  = progress.add_task(label, total=None)
    ok    = stream_download(url, dest, api.session, progress, task)
    progress.remove_task(task)

    if ok:
        if meta_fields is not None:
            if ext == "flac":
                embed_flac_metadata(dest, track, cover, meta_fields, force_main_album_artist, override_main_artist)
            elif ext == "mp3":
                embed_mp3_metadata(dest, track, cover, meta_fields, force_main_album_artist, override_main_artist)
        console.print(f"  [green]✓[/] {filename}")
    else:
        if dest.exists():
            dest.unlink(missing_ok=True)

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run helper
# ─────────────────────────────────────────────────────────────────────────────


def _dry_run_track_rows(
    tracks: List[Dict],
    out_dir: Path,
    track_tmpl: str,
    quality_id: str,
    skip_existing: bool,
    is_multidisc: bool,
) -> Tuple[List[Tuple[str, str, str]], int, int]:
    """Return (rows, would_download, already_exist) for a list of tracks.

    Each row is a tuple of (track_label, dest_path_str, status_markup).
    """
    rows: List[Tuple[str, str, str]] = []
    would_download = 0
    already_exist  = 0
    ext = EXT_MAP.get(quality_id, "flac")

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
        filename = clean_name(filename)

        if is_multidisc:
            dest = out_dir / f"Disc {disc_no}" / filename
        else:
            dest = out_dir / filename

        if dest.exists():
            status = "[dim]exists[/]"
            already_exist += 1
            if skip_existing:
                action = "[dim]skip[/]"
            else:
                action = "[yellow]overwrite[/]"
                would_download += 1
        else:
            status = "[green]new[/]"
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

    folder_name = safe_format(
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
    )
    out_dir = root_dir / folder_name

    disc_nos     = sorted({t.get("media_number", 1) for t in tracks})
    is_multidisc = len(disc_nos) > 1 and cfg.get("multi_disc", True)

    skip_existing = cfg.get("skip_existing", True)
    rows, would_download, already_exist = _dry_run_track_rows(
        tracks, out_dir, track_tmpl, quality_id, skip_existing, is_multidisc
    )

    # ── print summary panel ──────────────────────────────────────────────────
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
# Album download orchestrator
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

    artist  = get_artists(album)
    main_artist = override_main_artist or get_main_artist(album)
    title   = album.get("title", "Unknown Album")
    year    = get_year(album)
    genre   = album.get("genre", {}).get("name", "")
    label   = album.get("label", {}).get("name", "")
    quality = get_quality_tag(album)
    tracks  = album.get("tracks", {}).get("items", [])

    actual_artist_id = str(album.get("artist", {}).get("id", ""))

    if auto_override_id:
        artist_id_val = force_artist_id or actual_artist_id
    else:
        artist_id_val = actual_artist_id

    album_id_val  = str(album.get("id", album_id))

    # Attach full album dict to every track so metadata helpers work
    for t in tracks:
        t["album"] = album

    # Apply edition/version to titles if configured
    if cfg.get("include_version", False):
        apply_version_to_title(album)
        for t in tracks:
            apply_version_to_title(t)

    # Strip featured-artist text from titles if configured
    if cfg.get("strip_feat_from_album_title", False):
        strip_feat_from_album_title(album)
    if cfg.get("strip_feat_from_track_title", False):
        for t in tracks:
            strip_feat_from_track_title(t)

    folder_name = safe_format(
        folder_tmpl,
        artist    = artist,
        main_artist = main_artist,
        album     = album.get("title", "Unknown Album"),
        year      = year,
        genre     = genre,
        label     = label,
        quality   = quality,
        artist_id = artist_id_val,
        album_id  = album_id_val,
    )
    out_dir = root_dir / folder_name
    dbg(f"Album output dir → {out_dir}")

    # Detect multi-disc
    disc_nos    = sorted({t.get("media_number", 1) for t in tracks})
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

    # Resolve per-field metadata gates once for the whole album
    meta_flds = get_meta_fields(cfg)
    embed_cover_in_file = meta_flds is not None and meta_flds.get("cover", True)

    # Cover art — fetch if needed for saving to disk or embedding in files
    cover: Optional[bytes] = None
    if cfg.get("save_cover") or embed_cover_in_file:
        with console.status("Fetching cover art…"):
            cover = fetch_cover(album, api.session)

    if cfg.get("save_cover") and cover:
        cover_path = out_dir / "cover.jpg"
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        if not cover_path.exists():
            cover_path.write_bytes(cover)
            console.print("  [green]✓[/] cover.jpg")

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
                console.print(
                    f"  [yellow]⊘ Not streamable:[/] {track.get('title', '?')}"
                )
                continue

            disc = track.get("media_number", 1)
            if is_multidisc:
                track_dir = out_dir / f"Disc {disc}"
            else:
                track_dir = out_dir

            download_single_track(
                api           = api,
                track         = track,
                out_dir       = track_dir,
                track_tmpl    = track_tmpl,
                quality_id    = quality_id,
                cover         = cover,
                meta_fields   = meta_flds,
                skip_existing = cfg.get("skip_existing", True),
                progress      = progress,
                total_tracks  = len(tracks),
                force_main_album_artist = cfg.get("force_main_album_artist", False),
                override_main_artist    = override_main_artist,
            )

    console.print(f"\n[bold green]✓ Done![/]  →  {out_dir}\n")
    return artist_id_val


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("1.0.0", prog_name="qobuz-dl")
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose/debug output (API calls, file paths, metadata decisions).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """qobuz-dl — Download music from Qobuz via the official API.

    \b
    Quick start:
      1.  qobuz-dl setup
      2.  qobuz-dl search "Pink Floyd"
      3.  qobuz-dl dl https://open.qobuz.com/album/...

    Pass --verbose / -v before the subcommand to enable debug output:
      qobuz-dl --verbose dl https://open.qobuz.com/album/...
      qobuz-dl -v search "Radiohead"
    """
    global _VERBOSE
    _VERBOSE = verbose
    if verbose:
        console.print("[dim][DEBUG] Verbose mode enabled[/dim]")


# ── setup ─────────────────────────────────────────────────────────────────────


@cli.command()
def setup() -> None:
    """Interactive first-time setup wizard."""
    cfg = load_config()

    console.print(
        Panel(
            "[bold]qobuz-dl setup[/]\n\n"
            "You will need an [cyan]app_id[/], [cyan]secret[/] and at least one "
            "[cyan]auth token[/].\n"
            "These come from reverse-engineering the Qobuz desktop or mobile app.",
            border_style="blue",
        )
    )

    cfg["app_id"] = click.prompt("App ID  ", default=cfg.get("app_id", ""))
    cfg["secret"] = click.prompt("Secret  ", default=cfg.get("secret", ""))

    existing = ", ".join(cfg.get("auth_tokens", []))
    tokens_raw = click.prompt(
        "Auth token(s)  [comma-separated if multiple]",
        default=existing or "",
    )
    cfg["auth_tokens"] = [t.strip() for t in tokens_raw.split(",") if t.strip()]

    console.print()
    cfg["download_dir"] = click.prompt(
        "Default download directory",
        default=cfg.get("download_dir"),
    )

    console.print("\nAvailable quality levels:")
    for k, qid in QUALITY_MAP.items():
        console.print(f"  [cyan]{k:<14}[/] {QUALITY_LABELS[qid]}")

    cfg["quality"] = click.prompt(
        "\nDefault quality",
        default=cfg.get("quality", "hi-res-192"),
        type=click.Choice(list(QUALITY_MAP)),
    )

    console.print(TEMPLATE_HELP)

    cfg["folder_template"] = click.prompt(
        "Folder template",
        default=cfg.get("folder_template"),
    )
    cfg["track_template"] = click.prompt(
        "Track filename template  (no extension)",
        default=cfg.get("track_template"),
    )

    console.print()
    cfg["include_version"] = click.confirm("Include edition/version in album and track titles?", default=cfg.get("include_version", True))
    cfg["strip_feat_from_album_title"] = click.confirm("Try to strip featured artists from album titles?", default=cfg.get("strip_feat_from_album_title", False))
    cfg["strip_feat_from_track_title"] = click.confirm("Try to strip featured artists from track titles?", default=cfg.get("strip_feat_from_track_title", False))
    cfg["multi_disc"]     = click.confirm("Create Disc N/ subdirectories for multi-disc albums?", default=cfg.get("multi_disc", True))
    cfg["embed_metadata"] = click.confirm("Embed metadata tags in downloaded files?", default=cfg.get("embed_metadata", True))

    if cfg["embed_metadata"]:
        cfg["force_main_album_artist"] = click.confirm("  Set Album Artist tag to Main Artist only?", default=cfg.get("force_main_album_artist", False))

        current_fields = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}
        console.print(
            "\n[bold]Metadata fields[/] — choose which tags to embed in audio files.\n"
            "[dim]Note: 'cover' here means art embedded inside the file;\n"
            "      cover.jpg on disk is controlled by 'Save cover.jpg?' below.[/]\n"
        )
        set_all = click.confirm("  Set all fields at once?", default=False)
        if set_all:
            enable_all = click.confirm("  Enable all metadata fields?", default=True)
            cfg["metadata_fields"] = {k: enable_all for k in METADATA_FIELDS}
        else:
            fields: Dict[str, bool] = {}
            for field in METADATA_FIELDS:
                fields[field] = click.confirm(
                    f"  Embed {click.style(field, fg='cyan')}?",
                    default=current_fields.get(field, True),
                )
            cfg["metadata_fields"] = fields

    cfg["save_cover"]    = click.confirm("Save cover.jpg alongside tracks?", default=cfg.get("save_cover", True))
    cfg["skip_existing"] = click.confirm("Skip already-downloaded tracks?", default=cfg.get("skip_existing", True))

    socks = click.prompt(
        "\nSOCKS5 proxy  [host:port — leave blank for none]",
        default=cfg.get("socks5_proxy", ""),
    )
    cfg["socks5_proxy"] = socks.strip()

    save_config(cfg)
    console.print(f"\n[bold green]✓[/] Config saved → {CONFIG_FILE}")


# ── config ────────────────────────────────────────────────────────────────────


@cli.command("config")
@click.argument("key", required=False)
@click.argument("value", required=False)
def config_cmd(key: Optional[str], value: Optional[str]) -> None:
    """View or set a configuration value.

    \b
    Examples:
      qobuz-dl config                                 # print all settings
      qobuz-dl config download_dir                    # print one value
      qobuz-dl config download_dir ~/Music            # set a value
      qobuz-dl config quality cd
      qobuz-dl config folder_template "{artist}/{year} - {album}"

    \b
    Metadata fields use dot notation:
      qobuz-dl config metadata_fields                 # show all field toggles
      qobuz-dl config metadata_fields.copyright       # show one field
      qobuz-dl config metadata_fields.copyright false # disable copyright tag
      qobuz-dl config metadata_fields.all true        # enable every field
      qobuz-dl config metadata_fields.all false       # disable every field
    """
    cfg = load_config()

    # ── dot-notation: metadata_fields.FIELD ──────────────────────────────────
    if key and "." in key:
        parent, sub = key.split(".", 1)
        if parent != "metadata_fields":
            raise click.ClickException(f"Dot notation is only supported for metadata_fields, got '{parent}'")

        fields: Dict[str, bool] = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}

        if value is None:
            # Read: show a single field (or all if sub=="all")
            if sub == "all":
                t = Table(title="metadata_fields", border_style="blue", show_lines=False)
                t.add_column("Field",   style="cyan", no_wrap=True)
                t.add_column("Enabled", justify="center")
                for fname, fval in fields.items():
                    t.add_row(fname, "[green]✓[/]" if fval else "[red]✗[/]")
                console.print(t)
            else:
                if sub not in METADATA_FIELDS:
                    raise click.ClickException(
                        f"Unknown metadata field '{sub}'. "
                        f"Valid fields: {', '.join(METADATA_FIELDS)}"
                    )
                enabled = fields.get(sub, True)
                console.print(f"[cyan]metadata_fields.{sub}[/] = {json.dumps(enabled)}")
            return

        # Write
        bool_val = value.lower() in ("true", "1", "yes", "on")
        if sub == "all":
            cfg["metadata_fields"] = {k: bool_val for k in METADATA_FIELDS}
            save_config(cfg)
            state = "enabled" if bool_val else "disabled"
            console.print(f"[green]✓[/] All metadata fields {state}.")
        else:
            if sub not in METADATA_FIELDS:
                raise click.ClickException(
                    f"Unknown metadata field '{sub}'. "
                    f"Valid fields: {', '.join(METADATA_FIELDS)}"
                )
            fields[sub] = bool_val
            cfg["metadata_fields"] = fields
            save_config(cfg)
            console.print(f"[green]✓[/] metadata_fields.{sub} = {json.dumps(bool_val)}")
        return

    # ── plain key ─────────────────────────────────────────────────────────────
    if key is None:
        table = Table(title="qobuz-dl config", border_style="blue", show_lines=False)
        table.add_column("Key",   style="cyan", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for k, v in cfg.items():
            table.add_row(k, json.dumps(v))
        console.print(table)
        return

    if key == "metadata_fields" and value is None:
        # Pretty-print the fields sub-table when user types just "metadata_fields"
        fields = {**METADATA_FIELDS, **cfg.get("metadata_fields", {})}
        t = Table(title="metadata_fields", border_style="blue", show_lines=False)
        t.add_column("Field",   style="cyan", no_wrap=True)
        t.add_column("Enabled", justify="center")
        for fname, fval in fields.items():
            t.add_row(fname, "[green]✓[/]" if fval else "[red]✗[/]")
        console.print(t)
        return

    if value is None:
        console.print(f"[cyan]{key}[/] = {json.dumps(cfg.get(key, '<not set>'))}")
        return

    # Type-aware coercion
    if key == "auth_tokens":
        cfg[key] = [t.strip() for t in value.split(",") if t.strip()]
    elif key in ("embed_metadata", "save_cover", "skip_existing", "multi_disc", "include_version", "force_main_album_artist"):
        cfg[key] = value.lower() in ("true", "1", "yes", "on")
    else:
        cfg[key] = value

    save_config(cfg)
    console.print(f"[green]✓[/] {key} = {json.dumps(cfg[key])}")


# ── search ────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("-n", "--limit", default=10, show_default=True, help="Results per category")
@click.option(
    "-t", "--type", "search_type",
    type=click.Choice(["all", "albums", "tracks", "artists"]),
    default="all", show_default=True,
    help="Filter result type",
)
def search(query: str, limit: int, search_type: str) -> None:
    """Search Qobuz for albums, tracks, or artists.

    \b
    Examples:
      qobuz-dl search "Daft Punk"
      qobuz-dl search "Random Access Memories" -t albums -n 5
      qobuz-dl search "Get Lucky" -t tracks
    """
    cfg = load_config()
    api = QobuzAPI(cfg)

    with console.status("Searching…"):
        try:
            results = api.search(query, limit=limit)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    shown = 0

    if search_type in ("all", "albums"):
        items = results.get("albums", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Albums", border_style="blue", show_lines=True)
            t.add_column("#",       justify="right", style="dim", no_wrap=True)
            t.add_column("Artist",  style="cyan", max_width=28)
            t.add_column("Title",   max_width=35)
            t.add_column("Year",    justify="center", no_wrap=True)
            t.add_column("Quality", justify="center", no_wrap=True)
            t.add_column("Tracks",  justify="center", no_wrap=True)
            t.add_column("URL",     style="dim", overflow="fold")
            for i, a in enumerate(items, 1):
                bits = a.get("maximum_bit_depth", 0)
                rate = a.get("maximum_sampling_rate", 0)
                q    = f"{bits}b/{int(rate)}k" if bits and rate else "—"
                url  = f"https://open.qobuz.com/album/{a['id']}"
                t.add_row(
                    str(i),
                    get_artists(a),
                    a.get("title", ""),
                    get_year(a),
                    q,
                    str(a.get("tracks_count", "?")),
                    url,
                )
            console.print(t)

    if search_type in ("all", "tracks"):
        items = results.get("tracks", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Tracks", border_style="magenta", show_lines=True)
            t.add_column("#",      justify="right", style="dim", no_wrap=True)
            t.add_column("Artist", style="cyan", max_width=28)
            t.add_column("Title",  max_width=35)
            t.add_column("Album",  max_width=28)
            t.add_column("URL",    style="dim", overflow="fold")
            for i, tr in enumerate(items, 1):
                url = f"https://open.qobuz.com/track/{tr['id']}"
                t.add_row(
                    str(i),
                    tr.get("performer", {}).get("name", ""),
                    tr.get("title", ""),
                    tr.get("album", {}).get("title", ""),
                    url,
                )
            console.print(t)

    if search_type in ("all", "artists"):
        items = results.get("artists", {}).get("items", [])
        if items:
            shown += 1
            t = Table(title="Artists", border_style="green", show_lines=True)
            t.add_column("#",      justify="right", style="dim", no_wrap=True)
            t.add_column("Name",   style="cyan")
            t.add_column("Albums", justify="center", no_wrap=True)
            t.add_column("URL",    style="dim", overflow="fold")
            for i, a in enumerate(items, 1):
                url = f"https://open.qobuz.com/artist/{a['id']}"
                t.add_row(str(i), a.get("name", ""), str(a.get("albums_count", "?")), url)
            console.print(t)

    if not shown:
        console.print("[yellow]No results found.[/]")


# ── dl ────────────────────────────────────────────────────────────────────────


@cli.command("dl")
@click.argument("urls", nargs=-1, required=True, metavar="URL [URL …]")
@click.option("-d", "--dir",       "download_dir",     default=None, help="Override download directory")
@click.option("-q", "--quality",                       default=None, type=click.Choice(list(QUALITY_MAP)), help="Audio quality")
@click.option("-F", "--folder-template",               default=None, help="Folder naming template")
@click.option("-f", "--track-template",                default=None, help="Track filename template  (no extension)")
@click.option("--no-metadata",     "no_metadata",      is_flag=True, help="Skip metadata embedding")
@click.option("--no-cover",        "no_cover",         is_flag=True, help="Skip saving cover.jpg")
@click.option("--no-skip",         "no_skip",          is_flag=True, help="Re-download even if file exists")
@click.option("--dry-run",         "dry_run",          is_flag=True, help="Preview what would be downloaded — no files written")
@click.option("--override-main-artist",                default=None, help="Override the main artist (Album Artist) for this run")
@click.option("--override-artist-id",                  is_flag=True, help=(
    "Force a single artist_id across all downloads in this run. "
    "The ID is taken from the first artist URL / ar-id target supplied; "
    "if no artist target is given it is inferred from the first album or track processed. "
))
def dl(
    urls: Tuple[str, ...],
    download_dir: Optional[str],
    quality: Optional[str],
    folder_template: Optional[str],
    track_template: Optional[str],
    no_metadata: bool,
    no_cover: bool,
    no_skip: bool,
    dry_run: bool,
    override_main_artist: Optional[str],
    override_artist_id: bool,
) -> None:
    """Download one or more albums, tracks, or artist discographies.

    \b
    Accepts Qobuz URLs or bare IDs.  Pass multiple targets at once:

      qobuz-dl dl <url> <url2> ...
      qobuz-dl dl https://open.qobuz.com/album/0060253780948
      qobuz-dl dl https://open.qobuz.com/artist/5765466

    Bare-ID shortcuts (no URL needed):

      qobuz-dl dl ar-id 707261
      qobuz-dl dl al-id 0060253780948
      qobuz-dl dl tr-id 23929921
      qobuz-dl dl ar-id 707261 al-id 0060253780948

    Use --dry-run to preview what would be downloaded without writing any files:

      qobuz-dl dl ar-id 707261 --dry-run
      qobuz-dl dl al-id 0060253780948 --dry-run

    """ + TEMPLATE_HELP
    cfg = load_config()
    api = QobuzAPI(cfg)

    quality_id    = QUALITY_MAP.get(quality or cfg.get("quality", "hi-res-192"), "27")
    root_dir      = Path(download_dir or cfg.get("download_dir", str(Path.home() / "Music" / "Qobuz")))
    f_tmpl        = folder_template or cfg.get("folder_template", DEFAULT_CONFIG["folder_template"])
    t_tmpl        = track_template  or cfg.get("track_template",  DEFAULT_CONFIG["track_template"])

    effective_cfg = {
        **cfg,
        "embed_metadata": not no_metadata and cfg.get("embed_metadata", True),
        "save_cover":     not no_cover    and cfg.get("save_cover",     True),
        "skip_existing":  not no_skip     and cfg.get("skip_existing",  True),
    }

    if dry_run:
        console.print(
            Panel(
                "[bold yellow]Dry run[/] — resolving targets, no files will be written.",
                border_style="yellow",
            )
        )

    console.print(
        f"[dim]Quality:[/] {QUALITY_LABELS.get(quality_id, quality_id)}  "
        f"[dim]|  Root:[/] {root_dir}\n"
    )

    targets = parse_targets(urls)

    # Determine whether artist-ID forcing is active.
    # Requires at least one of the two override flags.
    auto_override_id: bool = override_artist_id or bool(override_main_artist)
    global_artist_id: Optional[str] = None

    if auto_override_id:
        # Collect every distinct artist target (URL or ar-id).
        explicit_artist_ids = {id_ for kind, id_ in targets if kind == "artist"}

        if len(explicit_artist_ids) > 1:
            raise click.ClickException(f"Multiple different artist IDs provided ({', '.join(explicit_artist_ids)}). Aborting to prevent collision.")
        global_artist_id = explicit_artist_ids.pop() if explicit_artist_ids else None

    for kind, id_ in targets:

        if kind == "album":
            if dry_run:
                res_id = dry_run_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id,
                )
            else:
                res_id = download_album(
                    api, id_, effective_cfg, quality_id, root_dir, f_tmpl, t_tmpl,
                    override_main_artist, global_artist_id, auto_override_id
                )
            if auto_override_id and not global_artist_id and res_id:
                global_artist_id = res_id

        elif kind == "track":
            console.print(f"\n[bold]Fetching track info…[/]")
            try:
                track = api.get_track(id_)
                album = track.get("album", {})
                if album.get("id"):
                    # Prefer full album info for metadata richness
                    try:
                        full_album = api.get_album(str(album["id"]))
                        track["album"] = full_album
                        album = full_album
                    except Exception:
                        pass

                # Apply edition/version to titles if configured
                if effective_cfg.get("include_version", False):
                    apply_version_to_title(track)
                    apply_version_to_title(album)

                # Strip featured-artist text from titles if configured
                if effective_cfg.get("strip_feat_from_track_title", False):
                    strip_feat_from_track_title(track)
                if effective_cfg.get("strip_feat_from_album_title", False):
                    strip_feat_from_album_title(album)

                artist = get_artists(album) or track.get("performer", {}).get("name", "")
                main_artist = override_main_artist or get_main_artist(album) or track.get("performer", {}).get("name", "")

                actual_artist_id = str(album.get("artist", {}).get("id", ""))

                if auto_override_id:
                    used_artist_id = global_artist_id or actual_artist_id
                else:
                    used_artist_id = actual_artist_id

                folder = safe_format(
                    f_tmpl,
                    artist    = artist,
                    main_artist = main_artist,
                    album     = album.get("title", ""),
                    year      = get_year(album),
                    genre     = album.get("genre", {}).get("name", ""),
                    label     = album.get("label", {}).get("name", ""),
                    quality   = get_quality_tag(album),
                    artist_id = used_artist_id,
                    album_id  = str(album.get("id", "")),
                )
                out_dir = root_dir / folder

                if dry_run:
                    # Resolve the track filename the same way download_single_track would
                    ext      = EXT_MAP.get(quality_id, "flac")
                    track_no = track.get("track_number", 0)
                    disc_no  = track.get("media_number", 1)
                    title    = track.get("title", "Unknown")
                    filename = safe_format(
                        t_tmpl,
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
                    filename = clean_name(filename)
                    dest     = out_dir / filename

                    exists = dest.exists()
                    skip   = effective_cfg.get("skip_existing", True)
                    if exists and skip:
                        action_markup = "[dim]skip (exists)[/]"
                    elif exists:
                        action_markup = "[yellow]overwrite[/]"
                    else:
                        action_markup = "[green]download[/]"

                    console.print(
                        Panel(
                            f"[bold]{artist}[/] — [italic]{title}[/]\n"
                            f"[dim]Dest:[/] {dest}\n"
                            f"Action: {action_markup}",
                            title="[bold blue]Dry Run — Track[/]",
                            border_style="blue",
                        )
                    )

                    if auto_override_id and not global_artist_id and actual_artist_id:
                        global_artist_id = actual_artist_id
                    continue

                track_meta_flds = get_meta_fields(effective_cfg)
                embed_cover_in_file = track_meta_flds is not None and track_meta_flds.get("cover", True)

                cover: Optional[bytes] = None
                if effective_cfg.get("save_cover") or embed_cover_in_file:
                    with console.status("Fetching cover art…"):
                        cover = fetch_cover(album, api.session)

                if effective_cfg.get("save_cover") and cover:
                    cp = out_dir / "cover.jpg"
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    if not cp.exists():
                        cp.write_bytes(cover)

                console.print(
                    Panel(
                        f"[bold]{artist}[/] — [italic]{track.get('title', '')}[/]",
                        title="[bold blue]Downloading Track[/]",
                        border_style="blue",
                    )
                )

                with Progress(
                    SpinnerColumn(), TextColumn("{task.description}"),
                    BarColumn(), DownloadColumn(), TransferSpeedColumn(),
                    TimeRemainingColumn(), console=console, transient=True,
                ) as progress:
                    download_single_track(
                        api           = api,
                        track         = track,
                        out_dir       = out_dir,
                        track_tmpl    = t_tmpl,
                        quality_id    = quality_id,
                        cover         = cover,
                        meta_fields   = track_meta_flds,
                        skip_existing = effective_cfg.get("skip_existing", True),
                        progress      = progress,
                        force_main_album_artist = effective_cfg.get("force_main_album_artist", False),
                        override_main_artist    = override_main_artist,
                    )

                console.print(f"\n[bold green]✓ Done![/]  →  {out_dir}\n")

                if auto_override_id and not global_artist_id and actual_artist_id:
                    global_artist_id = actual_artist_id

            except Exception as exc:
                console.print(f"[red]✗ {exc}[/]")

        elif kind == "artist":
            console.print(f"\n[bold]Fetching artist discography…[/]")
            try:
                for release_type in ("album", "epSingle", "live", "compilation"):
                    offset    = 0
                    page_size = 100
                    while True:
                        page = api.get_artist_releases(
                            id_,
                            release_type=release_type,
                            limit=page_size,
                            offset=offset,
                        )
                        items    = page.get("items", [])
                        has_more = page.get("has_more", False)
                        if not items:
                            break
                        console.print(
                            f"\n[bold]{release_type}[/] — "
                            f"{len(items)} release(s)"
                            + (" [dim](more available)[/]" if has_more else "")
                        )
                        for stub in items:
                            album_id = stub.get("id") or stub.get("qobuz_id")
                            if album_id:
                                if dry_run:
                                    res_id = dry_run_album(
                                        api, str(album_id), effective_cfg,
                                        quality_id, root_dir, f_tmpl, t_tmpl,
                                        override_main_artist, global_artist_id, auto_override_id,
                                    )
                                else:
                                    res_id = download_album(
                                        api, str(album_id), effective_cfg,
                                        quality_id, root_dir, f_tmpl, t_tmpl,
                                        override_main_artist, global_artist_id, auto_override_id
                                    )
                                if auto_override_id and not global_artist_id and res_id:
                                    global_artist_id = res_id
                        if not has_more:
                            break
                        offset += page_size

            except Exception as exc:
                console.print(f"[red]✗ Artist download error: {exc}[/]")

    if dry_run:
        console.print("\n[bold yellow]Dry run complete — nothing was downloaded.[/]\n")


# ── info ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("target", nargs=-1, required=True, metavar="URL | PREFIX ID")
def info(target: Tuple[str, ...]) -> None:
    """Show detailed info about an album or track without downloading.

    \b
    Accepts a Qobuz URL or a prefixed ID (al-id, tr-id):

      qobuz-dl info https://open.qobuz.com/album/0060253780948
      qobuz-dl info https://open.qobuz.com/track/23929921
      qobuz-dl info al-id 0060253780948
      qobuz-dl info tr-id 23929921
    """
    cfg  = load_config()
    api  = QobuzAPI(cfg)

    targets = parse_targets(target)
    if len(targets) != 1:
        raise click.ClickException("info accepts exactly one album or track target.")
    kind, id_ = targets[0]
    if kind == "artist":
        raise click.ClickException(
            "info does not support artist targets. Use an album or track URL/ID."
        )

    with console.status("Fetching info…"):
        try:
            if kind == "album":
                data = api.get_album(id_)
            elif kind == "track":
                data = api.get_track(id_)
            else:
                raise click.ClickException("Use an album or track URL with `info`.")
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc

    if kind == "album":
        tracks = data.get("tracks", {}).get("items", [])
        console.print(
            Panel(
                f"[bold]{get_artists(data)}[/] — [italic]{data.get('title', '')}[/]\n\n"
                f"Year     : {get_year(data)}\n"
                f"Genre    : {data.get('genre', {}).get('name', '')}\n"
                f"Label    : {data.get('label', {}).get('name', '')}\n"
                f"Tracks   : {len(tracks)}\n"
                f"Quality  : {get_quality_tag(data)}\n"
                f"UPC      : {data.get('upc', '')}\n"
                f"Streamable: {data.get('streamable', '?')}",
                title="Album Info",
                border_style="blue",
            )
        )
        t = Table(border_style="dim", show_lines=False)
        t.add_column("#",    justify="right", style="dim", no_wrap=True)
        t.add_column("D",    justify="center", style="dim")
        t.add_column("Title")
        t.add_column("Duration", justify="right", style="dim")
        t.add_column("Hi-Res",  justify="center")
        for tr in tracks:
            mins = tr.get("duration", 0) // 60
            secs = tr.get("duration", 0) % 60
            t.add_row(
                str(tr.get("track_number", "")),
                str(tr.get("media_number", 1)),
                tr.get("title", ""),
                f"{mins}:{secs:02d}",
                "✓" if tr.get("hires") else "",
            )
        console.print(t)
    else:
        album = data.get("album", {})
        mins  = data.get("duration", 0) // 60
        secs  = data.get("duration", 0) % 60
        console.print(
            Panel(
                f"[bold]{data.get('performer', {}).get('name', '')}[/] — "
                f"[italic]{data.get('title', '')}[/]\n\n"
                f"Album    : {album.get('title', '')}\n"
                f"Track #  : {data.get('track_number', '')}\n"
                f"Duration : {mins}:{secs:02d}\n"
                f"Hi-Res   : {data.get('hires', False)}\n"
                f"ISRC     : {data.get('isrc', '')}\n"
                f"Streamable: {data.get('streamable', '?')}",
                title="Track Info",
                border_style="magenta",
            )
        )


# ── completions ───────────────────────────────────────────────────────────────

_SHELL_INSTALL_PATHS: Dict[str, Path] = {
    "fish": Path.home() / ".config" / "fish" / "completions" / "qobuz-dl.fish",
    "bash": Path.home() / ".bash_completion.d" / "qobuz-dl",
    "zsh":  Path.home() / ".zfunc" / "_qobuz-dl",
}

_SHELL_ACTIVATE_HINTS: Dict[str, str] = {
    "fish": "Restart your shell, or run:  source ~/.config/fish/completions/qobuz-dl.fish",
    "bash": (
        "Add this line to ~/.bashrc, then run  source ~/.bashrc :\n"
        '  source "~/.bash_completion.d/qobuz-dl"'
    ),
    "zsh": (
        "Add these lines to ~/.zshrc, then run  source ~/.zshrc :\n"
        "  fpath=(~/.zfunc $fpath)\n"
        "  autoload -Uz compinit && compinit"
    ),
}


def _detect_shell() -> Optional[str]:
    """Guess the running shell from $SHELL."""
    name = Path(os.environ.get("SHELL", "")).name
    return name if name in _SHELL_INSTALL_PATHS else None


def _generate_completion_script(shell: str) -> str:
    """Ask Click to emit its native completion script for *shell*.

    Uses Click's public ``get_completion_class`` API (Click ≥ 8.1) to produce
    the script in-process — no subprocess needed, and works before the
    ``qobuz-dl`` entry-point is on PATH (e.g. during development).
    """
    from click.shell_completion import get_completion_class  # Click ≥ 8.0

    cls = get_completion_class(shell)
    if cls is None:
        raise click.ClickException(
            f"Click does not have a built-in completion class for '{shell}'.\n"
            "  Make sure Click ≥ 8.1 is installed."
        )
    complete = cls(cli, {}, "qobuz-dl", "_QOBUZ_DL_COMPLETE")
    script   = complete.source()
    if not script or not script.strip():
        raise click.ClickException(
            f"Completion script generation produced no output for shell '{shell}'."
        )
    return script


@cli.command("completions")
@click.option(
    "--shell", "shell_name",
    type=click.Choice(["fish", "bash", "zsh"]),
    default=None,
    help="Target shell.  Auto-detected from $SHELL when omitted.",
)
@click.option(
    "--install", is_flag=True,
    help="Write the script to the standard completions directory and show activation instructions.",
)
@click.option(
    "--print-only", is_flag=True,
    help="Print the raw completion script to stdout (overrides --install).",
)
def completions_cmd(shell_name: Optional[str], install: bool, print_only: bool) -> None:
    """Generate or install shell tab-completion scripts.

    \b
    One-shot install (auto-detects your shell):
      qobuz-dl completions --install

    Explicit shell:
      qobuz-dl completions --shell fish --install
      qobuz-dl completions --shell bash --install
      qobuz-dl completions --shell zsh  --install

    Print the raw script to stdout (pipe it wherever you like):
      qobuz-dl completions --shell fish --print-only

    \b
    Manual activation (if --install doesn't fit your setup):
      fish  →  _QOBUZ_DL_COMPLETE=fish_source qobuz-dl \\
                 > ~/.config/fish/completions/qobuz-dl.fish
      bash  →  eval "$(_QOBUZ_DL_COMPLETE=bash_source qobuz-dl)"   # add to ~/.bashrc
      zsh   →  eval "$(_QOBUZ_DL_COMPLETE=zsh_source  qobuz-dl)"   # add to ~/.zshrc
    """
    # ── resolve shell ─────────────────────────────────────────────────────────
    shell = shell_name
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            raise click.ClickException(
                f"Cannot auto-detect shell from $SHELL={os.environ.get('SHELL', '')!r}.\n"
                "  Pass --shell fish|bash|zsh explicitly."
            )
        console.print(f"[dim]Auto-detected shell:[/] {shell}")

    # ── generate script ───────────────────────────────────────────────────────
    with console.status(f"Generating {shell} completion script…"):
        try:
            script = _generate_completion_script(shell)
        except subprocess.TimeoutExpired:
            raise click.ClickException("Timed out while generating completion script.")

    dbg(f"Completion script — {len(script)} chars, first line: {script.splitlines()[0]!r}")

    # ── print-only mode ───────────────────────────────────────────────────────
    if print_only:
        click.echo(script)
        return

    # ── install mode ──────────────────────────────────────────────────────────
    if install:
        dest = _SHELL_INSTALL_PATHS[shell]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(script + "\n")
        console.print(f"[green]✓[/] Completion script written → [cyan]{dest}[/]")
        console.print()
        console.print(_SHELL_ACTIVATE_HINTS[shell])
        return

    # ── default: print script + hint ─────────────────────────────────────────
    click.echo(script)
    console.print()
    console.print(
        Panel(
            f"[bold]Pipe this into your shell's completions directory, or run:[/]\n\n"
            f"  [cyan]qobuz-dl completions --shell {shell} --install[/]\n\n"
            + _SHELL_ACTIVATE_HINTS[shell],
            title="[bold blue]Activate completions[/]",
            border_style="blue",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    cli()
