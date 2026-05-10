"""
qobuz_dl/gui/windows/main_window.py — Application main window.

NOT IMPLEMENTED — skeleton only.

MainWindow (QMainWindow)
────────────────────────
The root widget.  Contains a QTabWidget with three tabs:

  Tab 0 — "Search"    : SearchPanel widget
  Tab 1 — "Queue"     : DownloadQueuePanel widget
  Tab 2 — "Settings"  : inline config form (or a button that opens SetupDialog)

Layout
~~~~~~
  ┌─────────────────────────────────────────────────┐
  │  [Search]  [Queue (3)]  [Settings]       ⚙  ─ □ │
  ├─────────────────────────────────────────────────┤
  │                                                 │
  │   <active tab content>                          │
  │                                                 │
  ├─────────────────────────────────────────────────┤
  │  Status bar: "Ready" / "Downloading 2 of 7…"   │
  └─────────────────────────────────────────────────┘

Responsibilities
────────────────
• Constructs a Bridge instance and passes it to child widgets so they
  share a single API client and config.
• Listens to DownloadQueuePanel.queue_count_changed signal and updates
  the tab badge ("Queue (3)").
• Saves and restores window geometry via QSettings on close/open.
• Shows SetupDialog on first launch (when app_id is empty in config).
• Provides a status_message(str, timeout_ms) slot that child widgets
  emit to show one-line feedback in the status bar.

Signals emitted (for child widgets to connect to)
──────────────────────────────────────────────────
None — MainWindow is the root; it connects to child signals.

Slots to implement
──────────────────
  _on_download_enqueued(album_id_or_url: str) → None
      Called when SearchPanel emits download_requested.
      Passes the ID to DownloadQueuePanel and switches to the Queue tab.

  _on_settings_changed() → None
      Called after SetupDialog is accepted.
      Calls bridge.reload_config() so the new credentials take effect.
"""

from __future__ import annotations


class MainWindow:  # pragma: no cover — not implemented
    """QMainWindow for qobuz-dl.  NOT IMPLEMENTED."""

    def __init__(self) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
