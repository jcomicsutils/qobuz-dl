"""
qobuz_dl/gui/widgets/info_panel.py — Album/track metadata viewer.

NOT IMPLEMENTED — skeleton only.

InfoPanel (QWidget)
───────────────────
A read-only panel showing the metadata returned by Bridge.get_album_info()
or Bridge.get_track_info().  Displayed as a docked side panel or a small
modal dialog — the caller decides.

Layout (album view)
~~~~~~~~~~~~~~~~~~~
  ┌─────────────────────────────────────────────────┐
  │  [cover art 200×200]                            │
  │                                                 │
  │  Artist — Album title (2024)                    │
  │  Genre · Label · Quality · N tracks             │
  │                                                 │
  │  #   D   Title              Duration   Hi-Res   │
  │  1   1   Track one          3:42         ✓      │
  │  2   1   Track two          4:11               │
  │  …                                              │
  │                               [Download album]  │
  └─────────────────────────────────────────────────┘

Cover art
~~~~~~~~~
  Fetched asynchronously via a simple QThread or QThreadPool job that
  calls requests.get(cover_url).  On success, set as a QPixmap on a
  QLabel.  On failure, show a placeholder grey rect.

[Download album] button
~~~~~~~~~~~~~~~~~~~~~~~
  Emits download_requested(album_url: str) which the parent (SearchPanel
  or MainWindow) connects to DownloadQueuePanel.enqueue().

Signals
~~~~~~~
  download_requested = pyqtSignal(str)
"""

from __future__ import annotations


class InfoPanel:  # pragma: no cover — not implemented
    """Album / track metadata viewer.  NOT IMPLEMENTED."""

    def __init__(self, bridge, parent=None) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
