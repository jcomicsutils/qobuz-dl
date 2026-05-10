"""
qobuz_dl/gui/windows/setup_dialog.py — Credentials and preferences dialog.

NOT IMPLEMENTED — skeleton only.

SetupDialog (QDialog)
─────────────────────
A modal dialog equivalent to `qobuz-dl setup`.  Opens automatically on
first launch (when app_id is blank) and is accessible via the Settings tab
or a toolbar button at any time.

Layout (QTabWidget inside QDialog)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Tab 0 — "Credentials"
    • App ID          (QLineEdit)
    • Secret          (QLineEdit, echo mode Password)
    • Auth token(s)   (QPlainTextEdit, one per line)
    • [Test connection] button → calls api.search("test") to verify credentials
      and shows a green tick or red error inline

  Tab 1 — "Download"
    • Download directory  (QLineEdit + [Browse] button → QFileDialog)
    • Quality             (QComboBox: mp3 / cd / hi-res / hi-res-192)
    • Quality fallback    (QCheckBox)
    • Fallback path       (QListWidget with drag-to-reorder quality items,
                           enabled only when fallback checkbox is checked)
    • On final failure    (QComboBox: keep_partial / delete_partial / delete_album)
    • Retries             (QSpinBox 0–20)

  Tab 2 — "Metadata"
    • Embed metadata      (QCheckBox, master toggle)
    • Per-field grid      (QCheckBox for each METADATA_FIELDS key,
                           disabled when master toggle is off)
    • Force main album artist  (QCheckBox)
    • Include version     (QCheckBox)
    • Strip feat. from album titles / track titles  (QCheckBox × 2)

  Tab 3 — "Filenames"
    • Folder template     (QLineEdit with placeholder and variable reference)
    • Track template      (QLineEdit)
    • Save cover.jpg      (QCheckBox)
    • Cover size          (QComboBox: thumbnail / small / large / original)
    • Truncate filenames  (QCheckBox)
    • Filename max bytes  (QSpinBox 16–255)
    • Truncate position   (QComboBox: end / middle)
    • Truncation marker   (QLineEdit)
    • Same four controls repeated for folder names

Button box
~~~~~~~~~~
  [Cancel]  [Save]
  Save calls save_config(cfg) and emits accepted().
  Cancel discards all changes (work on a copy of the dict, not the live one).

Validation
~~~~~~~~~~
  • App ID and Secret must not be empty before Save is allowed.
  • At least one auth token must be present.
  • Folder and track templates must survive safe_format() with dummy values
    without raising; show an inline warning label if they don't.
"""

from __future__ import annotations


class SetupDialog:  # pragma: no cover — not implemented
    """Credentials and preferences dialog.  NOT IMPLEMENTED."""

    def __init__(self, parent=None) -> None:
        raise NotImplementedError("See CONTRIBUTING_GUI.md")
