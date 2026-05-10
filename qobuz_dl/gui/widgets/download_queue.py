"""
qobuz_dl/gui/widgets/download_queue.py — Download queue tab content.

NOT IMPLEMENTED — skeleton only.

DownloadQueuePanel (QWidget)
────────────────────────────
The content of the "Queue" tab.  Shows all pending, active, and
completed downloads in a single scrollable list.

Layout
~~~~~~
  ┌─────────────────────────────────────────────────┐
  │  [+ Add URL]           [Start all]  [Clear done]│  ← toolbar
  ├─────────────────────────────────────────────────┤
  │  ┌──────────────────────────────────────────┐   │
  │  │ ▶ Artist — Album (2024)   [████░░░] 42%  │   │  ← QueueItem widget
  │  │   Track 3/12: "Song title"  1.2 MB/s     │   │
  │  │                               [✕ Cancel] │   │
  │  ├──────────────────────────────────────────┤   │
  │  │ ✓ Other Artist — EP         [completed]  │   │
  │  ├──────────────────────────────────────────┤   │
  │  │ ⏸ Album name                [queued]     │   │
  │  └──────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────┘

QueueItem (QWidget, used as a custom list row)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Each item holds:
    • A label: "Artist — Album (year)"
    • A QProgressBar (0–100, or indeterminate while fetching album info)
    • A sub-label: "Track N/total: <title>  <speed>"
    • A [Cancel] QPushButton
    • A status icon: ⏸ queued / ▶ active / ✓ done / ✗ failed

  When [Cancel] is clicked, it calls cancel_event.set() on the associated
  DownloadWorker.  The worker detects this each chunk and returns early.

Behaviour
~~~~~~~~~
  enqueue(url_or_id: str) → None
      Public slot.  Parses the string via parse_targets(), resolves it to
      an album or track ID using Bridge, creates a QueueItem in "queued"
      state, and adds it to the list.

  _start_next() → None
      Internal.  Pops the first queued item and submits a DownloadWorker
      to QThreadPool.  Called when an item completes and the queue is
      non-empty.  Configurable concurrency (from cfg["concurrency"], default 1).

  _on_progress(item_id, bytes_done, total) → None
      Slot connected to DownloadWorker.progress signal.  Updates the
      matching QueueItem's QProgressBar and sub-label.

  _on_track_started(item_id, track_title, track_index, total_tracks) → None
      Updates the sub-label so the user can see which track is downloading.

  _on_finished(item_id, success) → None
      Marks the item done (✓) or failed (✗).  Calls _start_next().

Signals
~~~~~~~
  queue_count_changed = pyqtSignal(int)
      Emitted whenever the number of pending + active items changes.
      MainWindow uses this to update the tab badge.
"""

from __future__ import annotations


class DownloadQueuePanel:  # pragma: no cover — not implemented
    """Download queue tab widget.  NOT IMPLEMENTED."""

    def __init__(self, bridge, parent=None) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
