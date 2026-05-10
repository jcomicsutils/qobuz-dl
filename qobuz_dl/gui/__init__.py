"""
qobuz_dl/gui/__init__.py — GUI package entry point.

NOT IMPLEMENTED — skeleton only.

This module exposes `main()`, which is registered as the `qobuz-dl-gui`
console script in pyproject.toml under [project.optional-dependencies] gui.

It is intentionally never imported by any CLI module, so users without
PyQt6 installed are never affected.

Implementation notes
────────────────────
`main()` should:
  1. Construct a QApplication (passing sys.argv).
  2. Apply a platform-appropriate style (Fusion works well cross-platform).
  3. Auto-detect the system light/dark preference and set a QPalette.
  4. Install a top-level exception handler that shows a QMessageBox instead
     of crashing silently.
  5. Construct and show MainWindow.
  6. Call sys.exit(app.exec()).

Guard the import so the rest of the package never fails on a machine
without PyQt6:

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit(
            "PyQt6 is required for the GUI.  "
            "Install it with:  pip install qobuz-dl[gui]"
        ) from exc
"""

from __future__ import annotations


def main() -> None:
    """Launch the qobuz-dl GUI application.

    NOT IMPLEMENTED.
    """
    raise NotImplementedError(
        "The GUI has not been implemented yet.  "
        "See CONTRIBUTING_GUI.md for the design and CONTRIBUTING.md for how to help."
    )
