"""
qobuz_dl/gui/app.py — QApplication construction and global setup.

NOT IMPLEMENTED — skeleton only.

Responsibilities
────────────────
QobuzApp (subclass of QApplication)
    • Sets applicationName / applicationVersion / organizationName so Qt's
      QSettings finds the right path on every platform.
    • Detects the OS light/dark preference (via QPalette or platform APIs)
      and applies a matching QPalette so the GUI respects the system theme
      without a third-party theme library.
    • Installs sys.excepthook so unhandled exceptions show a QMessageBox
      with a traceback instead of crashing silently.
    • Provides a `restart()` helper that closes all windows and re-execs
      the process (useful after a credentials change in SetupDialog).

Usage (called from main() in __init__.py):
    app = QobuzApp(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

Dark mode detection notes
─────────────────────────
  Windows: QApplication.styleHints().colorScheme() (Qt ≥ 6.5)
            or compare QPalette window / windowText lightness.
  macOS:   same Qt 6.5 API, or check NSAppearance via ctypes if needed.
  Linux:   read the 'color-scheme' XDG setting via QDBus (freedesktop),
            or fall back to QPalette lightness heuristic.
"""

from __future__ import annotations


class QobuzApp:  # pragma: no cover — not implemented
    """QApplication subclass for qobuz-dl.

    NOT IMPLEMENTED.

    Parameters
    ----------
    argv:
        sys.argv passed through to QApplication.
    """

    def __init__(self, argv: list[str]) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
