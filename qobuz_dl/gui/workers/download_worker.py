"""
qobuz_dl/gui/workers/download_worker.py — Off-thread download worker.

NOT IMPLEMENTED — skeleton only.

DownloadSignals (QObject)
─────────────────────────
Companion signals object (see search_worker.py for the rationale).

  progress(int, int)
      Emitted per chunk: (bytes_written, total_bytes).
      DownloadQueuePanel uses this to advance QProgressBar.

  track_started(str, int, int)
      Emitted when a new track begins: (track_title, track_index, total_tracks).

  finished(bool)
      Emitted when the entire album/track download completes.
      True = all tracks succeeded, False = at least one failed.

  error(str)
      Emitted on a fatal error (failed to fetch album info, auth error, etc.)
      before any downloading begins.  Distinguished from per-track failures
      which are reported via finished(False).

DownloadWorker (QRunnable)
──────────────────────────
  __init__(bridge, target_url_or_id, cfg, cancel_event)
      bridge          — Bridge instance (shared with UI thread; Bridge methods
                        are read-only after __init__ so thread safety is fine)
      target_url_or_id — a Qobuz URL or "al-id/tr-id" prefixed ID string
      cfg             — copy of the config dict at the time of enqueue
                        (copy, not reference — user may change settings mid-queue)
      cancel_event    — threading.Event; set by the Cancel button

  run() → None
      1. Resolves target_url_or_id to (kind, id) via parse_targets().
      2. Fetches album/track info via bridge.get_album_info() or get_track_info().
      3. Calls bridge.download_track() for each track, passing:
           on_progress = lambda done, total: self.signals.progress.emit(done, total)
           cancel_event = self.cancel_event
      4. Emits track_started before each track.
      5. Emits finished(all_ok) when the loop ends.
      6. Checks cancel_event.is_set() before each track; if set, stops the
         loop and emits finished(False).

Cancellation contract
─────────────────────
  The cancel_event is also passed through to stream_download (via the
  on_progress callback path described in CONTRIBUTING_GUI.md).  This means
  cancellation is checked both between tracks (in this worker) and within
  a single track's chunk loop (in stream_download).  The partial file is
  handled by on_final_failure from the config.

Thread safety note
──────────────────
  Never call any Qt widget method from run().  Emit signals only.
  The connection type defaults to Qt.ConnectionType.QueuedConnection
  when emitting across threads, which is what we want.
"""

from __future__ import annotations
import threading


class DownloadWorker:  # pragma: no cover — not implemented
    """QRunnable that downloads one album or track off the main thread.

    NOT IMPLEMENTED.
    """

    def __init__(
        self,
        bridge,
        target: str,
        cfg: dict,
        cancel_event: threading.Event,
    ) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")

    def run(self) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
