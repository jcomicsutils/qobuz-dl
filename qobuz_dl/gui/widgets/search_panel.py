"""
qobuz_dl/gui/widgets/search_panel.py — Search tab content.

NOT IMPLEMENTED — skeleton only.

SearchPanel (QWidget)
─────────────────────
The content of the "Search" tab in MainWindow.

Layout
~~~~~~
  ┌─────────────────────────────────────────────────┐
  │  [_____ search query _____]  [Albums ▾]  [Go]  │  ← search bar row
  ├─────────────────────────────────────────────────┤
  │  Albums                                         │
  │  ┌───┬──────────────┬──────────────┬─────┬───┐  │
  │  │ # │ Artist       │ Title        │Year │ ▶ │  │  ← QTableWidget
  │  └───┴──────────────┴──────────────┴─────┴───┘  │
  │  Tracks                                         │
  │  ┌───┬──────────────┬──────────────┬──────────┐  │
  │  │ # │ Artist       │ Title        │ Album    │  │
  │  └───┴──────────────┴──────────────┴──────────┘  │
  └─────────────────────────────────────────────────┘

Behaviour
~~~~~~~~~
  • Pressing Enter in the search box or clicking [Go] launches a
    SearchWorker on QThreadPool.
  • While the worker runs, [Go] is disabled and a QProgressBar in
    indeterminate mode spins in the status bar.
  • On results_ready the tables are populated.  Empty sections are hidden.
  • On error, a QMessageBox.warning is shown.
  • Double-clicking a row emits download_requested(str) — the album or
    track URL.  Right-clicking shows a context menu with "Download",
    "Copy URL", and "View info".
  • "View info" calls Bridge.get_album_info / get_track_info and opens
    InfoPanel as a floating dock or a small dialog.

Signals
~~~~~~~
  download_requested = pyqtSignal(str)
      Emitted with a Qobuz URL string when the user requests a download.
      MainWindow connects this to DownloadQueuePanel.enqueue(url).
"""

from __future__ import annotations


class SearchPanel:  # pragma: no cover — not implemented
    """Search tab widget.  NOT IMPLEMENTED."""

    def __init__(self, bridge, parent=None) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
