"""
constants.py — Static constants and default configuration values.
No local imports; safe to import from anywhere in the package.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".config" / "qobuz-dl"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ─────────────────────────────────────────────────────────────────────────────
# URL patterns
# ─────────────────────────────────────────────────────────────────────────────

ALBUM_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/album/([a-zA-Z0-9]+)")
TRACK_URL_RE  = re.compile(r"https?://(?:play|open)\.qobuz\.com/track/(\d+)")
ARTIST_URL_RE = re.compile(r"https?://(?:play|open)\.qobuz\.com/artist/(\d+)")

# ─────────────────────────────────────────────────────────────────────────────
# Quality maps
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# Filesystem
# ─────────────────────────────────────────────────────────────────────────────

ILLEGAL_CHARS = r'/\?:*"<>|'

# ─────────────────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────────────────

# Canonical metadata field names and their defaults.
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

# ─────────────────────────────────────────────────────────────────────────────
# Default config
# ─────────────────────────────────────────────────────────────────────────────

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
    "retries":         3,
    "on_final_failure": "delete_partial",  # "keep_partial" | "delete_partial" | "delete_album"
    "socks5_proxy":    "",
    "include_version": True,
    "force_main_album_artist": False,
    "strip_feat_from_album_title": False,
    "strip_feat_from_track_title": False,
    # ── name truncation ───────────────────────────────────────────────────────
    "truncate_folder":          True,
    "folder_truncate_pos":      "end",    # "middle" | "end"
    "folder_truncate_marker":   "",
    "folder_max_bytes":         255,
    "truncate_filename":        True,
    "filename_truncate_pos":    "end",    # "middle" | "end"
    "filename_truncate_marker": "...",
    "filename_max_bytes":       255,
}

# ─────────────────────────────────────────────────────────────────────────────
# Help text
# ─────────────────────────────────────────────────────────────────────────────

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
