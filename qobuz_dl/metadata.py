"""
metadata.py — Cover art fetching and audio metadata embedding (FLAC & MP3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import requests

from .utils import console, dbg, get_artists, get_main_artist, get_year


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
# Tag embedding
# ─────────────────────────────────────────────────────────────────────────────

def embed_flac_metadata(
    path: Path,
    track: Dict,
    cover: Optional[bytes],
    fields: Dict[str, bool],
    force_main_album_artist: bool = False,
    override_main_artist: Optional[str] = None,
) -> None:
    """Write Vorbis comment tags to a FLAC file, respecting per-field gates."""
    f = fields
    dbg(f"Embedding FLAC metadata → {path.name}  enabled_fields={[k for k,v in f.items() if v]}")
    try:
        from mutagen.flac import FLAC, Picture  # type: ignore

        audio = FLAC(path)
        album = track.get("album", {})
        artist = (
            get_artists(album) if album.get("artists") else
            track.get("performer", {}).get("name", "")
        )
        album_artist_val = override_main_artist or (
            get_main_artist(album) if force_main_album_artist else get_artists(album)
        )

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
    path: Path,
    track: Dict,
    cover: Optional[bytes],
    fields: Dict[str, bool],
    force_main_album_artist: bool = False,
    override_main_artist: Optional[str] = None,
) -> None:
    """Write ID3 tags to an MP3 file, respecting per-field gates."""
    f = fields
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
        album_artist_val = override_main_artist or (
            get_main_artist(album) if force_main_album_artist else get_artists(album)
        )

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
