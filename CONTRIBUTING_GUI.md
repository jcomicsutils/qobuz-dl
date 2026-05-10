# GUI Contributor Guide

> **Status: Not implemented — skeleton only.**
> Every file in `qobuz_dl/gui/` is a documented stub.  Nothing here runs.
> This guide explains the intended design so a contributor can implement
> the GUI without having to reverse-engineer the CLI codebase.

---

## Overview

The GUI is an **optional** layer on top of the existing CLI engine.
The core modules (`api.py`, `downloader.py`, `metadata.py`, `config.py`,
`utils.py`) are left entirely untouched — the GUI calls them directly,
the same way the CLI commands do.

Installing:
```bash
pip install qobuz-dl[gui]     # installs PyQt6
pip install qobuz-dl          # CLI only — PyQt6 never imported
```

Launching:
```bash
qobuz-dl-gui
```

---

## Architecture

```
qobuz_dl/
  gui/
    __init__.py          # main() entry point
    app.py               # QApplication setup, theme, exception handling
    bridge.py            # thin adapter: wraps core API + downloader for Qt signals
    windows/
      main_window.py     # QMainWindow: tab container
      setup_dialog.py    # QDialog: credentials + preferences
    widgets/
      search_panel.py    # search bar + results table
      download_queue.py  # queue list + per-item progress bars
      info_panel.py      # album/track metadata viewer
    workers/
      download_worker.py # QRunnable: runs download_single_track off-thread
      search_worker.py   # QRunnable: runs api.search off-thread
```

The GUI **never** calls `cli/` code.  It calls `api.py`, `downloader.py`,
`config.py`, and `utils.py` directly.

---

## The one required core change

Before implementing the GUI, make this change to `downloader.py`.
It is backward-compatible — the CLI path is unaffected.

Add an optional `on_progress` callback to `stream_download` and
`download_single_track`:

```python
# downloader.py — stream_download signature change
from typing import Callable, Optional

def stream_download(
    url: str,
    dest: Path,
    session: requests.Session,
    progress: Progress,
    task: TaskID,
    retries: int = 3,
    url_fetcher=None,
    on_progress: Optional[Callable[[int, int], None]] = None,
    # ^^^ NEW: called with (bytes_written, total_bytes) on each chunk
) -> Tuple[bool, bool]:
    ...
    for chunk in r.iter_content(chunk_size=131072):
        if chunk:
            f.write(chunk)
            written += len(chunk)
            progress.advance(task, len(chunk))
            if on_progress:                          # NEW
                on_progress(written, total)          # NEW
```

The CLI passes `on_progress=None` (the default) and nothing changes.
The GUI passes a lambda that emits a Qt signal.

Also add `cancel_event: Optional[threading.Event] = None` so the GUI
can cancel an in-flight download cleanly:

```python
for chunk in r.iter_content(chunk_size=131072):
    if cancel_event and cancel_event.is_set():   # NEW
        return False, False                       # NEW
    ...
```

---

## Threading model

**Rule: no network or file I/O on the main thread, ever.**

Use `QThreadPool` with `QRunnable` workers.  Each worker emits Qt signals
back to the UI thread via a companion `QObject` (signals cannot live on
`QRunnable` directly).

```
Main thread (Qt event loop)
  └─ QThreadPool
       ├─ SearchWorker(QRunnable)   → emits: results_ready(list), error(str)
       └─ DownloadWorker(QRunnable) → emits: progress(int, int), finished(bool), error(str)
```

Workers receive a `threading.Event` for cancellation.
The cancel button calls `event.set()`; the worker checks it each chunk.

---

## Config

Use `qobuz_dl.config.load_config()` and `save_config()` directly.
The `SetupDialog` is just a Qt form over the same dict the CLI wizard
writes.  No separate GUI config file.

---

## Tests

Tests live in `tests/gui/` and require `pytest-qt`:
```bash
pip install qobuz-dl[dev]   # already includes pytest-qt
pytest tests/gui/ -v
```

See each `tests/gui/test_*.py` stub for what each suite should cover.

---

## Not in scope (for a first implementation)

- Drag-and-drop URL targets
- System tray / background downloading
- macOS menu bar extras
- Themes beyond light/dark auto-detect

These are listed in `TODO.md` and should be tackled after the core GUI works.
