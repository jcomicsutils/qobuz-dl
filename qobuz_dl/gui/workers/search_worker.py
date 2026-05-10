"""
qobuz_dl/gui/workers/search_worker.py — Off-thread search worker.

NOT IMPLEMENTED — skeleton only.

Why two objects are needed
──────────────────────────
PyQt6 signals must live on a QObject.  QRunnable is not a QObject.
The idiomatic solution is a companion Signals object:

    class SearchSignals(QObject):
        results_ready = pyqtSignal(object)   # SearchResult dataclass
        error         = pyqtSignal(str)

    class SearchWorker(QRunnable):
        def __init__(self, bridge, query, limit, search_type):
            super().__init__()
            self.signals = SearchSignals()
            ...

        def run(self):
            try:
                result = self.bridge.search(self.query, self.limit, self.search_type)
                self.signals.results_ready.emit(result)
            except BridgeError as exc:
                self.signals.error.emit(exc.message)

Usage (from SearchPanel):
    worker = SearchWorker(self.bridge, query, limit, search_type)
    worker.signals.results_ready.connect(self._on_results)
    worker.signals.error.connect(self._on_search_error)
    QThreadPool.globalInstance().start(worker)

SearchSignals
─────────────
  results_ready(SearchResult)
      Emitted with the parsed result on success.

  error(str)
      Emitted with a human-readable message on failure.
      SearchPanel should show this in a QMessageBox.warning().

SearchWorker
────────────
  __init__(bridge, query, limit, search_type)
  run() → None
      Calls bridge.search() and emits the appropriate signal.
      Must not touch any Qt widgets directly (wrong thread).
"""

from __future__ import annotations


class SearchWorker:  # pragma: no cover — not implemented
    """QRunnable that calls Bridge.search off the main thread.  NOT IMPLEMENTED."""

    def __init__(self, bridge, query: str, limit: int, search_type: str) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")

    def run(self) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
