"""
qobuz_dl/gui/bridge.py — Thin adapter between the core engine and Qt.

NOT IMPLEMENTED — skeleton only.

Why this module exists
──────────────────────
The CLI uses Click + Rich for I/O.  The GUI needs Qt signals/slots instead.
Rather than modifying the core modules, this bridge:

  1. Wraps QobuzAPI so callers never deal with raw dicts.
  2. Converts the `on_progress` callback (added to downloader.py — see
     CONTRIBUTING_GUI.md) into a Qt signal emission.
  3. Translates ClickException / requests.HTTPError into friendly strings
     suitable for display in a QMessageBox or status bar.

Classes
───────
Bridge
    Holds a QobuzAPI instance (constructed from load_config()) and exposes
    typed methods the GUI calls directly.  All methods are synchronous and
    meant to be called from worker threads, not the main thread.

    Methods:
        search(query, limit, search_type) → SearchResult
            Calls api.search() and returns a typed dataclass instead of a
            raw dict.  Raises BridgeError on failure.

        get_album_info(album_id) → AlbumInfo
            Calls api.get_album() and returns a typed dataclass.

        get_track_info(track_id) → TrackInfo
            Calls api.get_track().

        download_track(track, out_dir, quality_id, ..., on_progress, cancel)
            Calls download_single_track() with the on_progress callback
            wired through.  Returns True on success.

        reload_config()
            Re-reads config from disk.  Call this after SetupDialog saves.

BridgeError(Exception)
    Raised by Bridge methods instead of ClickException or raw HTTP errors.
    Has a human-readable `message` attribute safe to show in a QMessageBox.

Typed result dataclasses
────────────────────────
Use @dataclass(frozen=True) for immutability:

    @dataclass(frozen=True)
    class AlbumInfo:
        id: str
        title: str
        artist: str
        year: str
        quality: str
        track_count: int
        tracks: list[TrackInfo]

    @dataclass(frozen=True)
    class TrackInfo:
        id: str
        title: str
        track_number: int
        disc_number: int
        duration_seconds: int
        streamable: bool

    @dataclass(frozen=True)
    class SearchResult:
        albums:  list[AlbumInfo]
        tracks:  list[TrackInfo]
        artists: list[ArtistInfo]
"""

from __future__ import annotations


class BridgeError(Exception):
    """Human-readable error from Bridge.  NOT IMPLEMENTED."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Bridge:  # pragma: no cover — not implemented
    """Adapter between QobuzAPI/downloader and the Qt GUI.

    NOT IMPLEMENTED.
    """

    def __init__(self) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
