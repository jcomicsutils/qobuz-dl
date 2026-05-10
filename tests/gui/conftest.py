"""
tests/gui/conftest.py — Shared fixtures for all GUI tests.

NOT IMPLEMENTED — these fixtures need to be fleshed out alongside
the actual widget implementations they support.

Fixtures
────────

pytestmark
    All tests in tests/gui/ are marked with `pytest.mark.gui` so they can
    be excluded from fast CI runs with `-m "not gui"`.

pyqt6_skip
    A module-level autouse fixture that calls pytest.importorskip("PyQt6")
    so the entire test file is skipped gracefully on machines without PyQt6,
    rather than failing with an ImportError.

mock_bridge (function scope)
    Returns a MagicMock that quacks like a Bridge instance.
    Pre-configured with sensible return values:

        mock_bridge.search.return_value = SearchResult(
            albums=[
                AlbumInfo(id="abc123", title="Test Album", artist="Test Artist",
                           year="2023", quality="FLAC 24bit 96kHz", track_count=10,
                           tracks=[...])
            ],
            tracks=[],
            artists=[],
        )
        mock_bridge.get_album_info.return_value = AlbumInfo(...)
        mock_bridge.get_track_info.return_value = TrackInfo(...)
        mock_bridge.download_track.return_value = True

    Tests that need different behaviour override specific attributes.

mock_bridge_error (function scope)
    A mock_bridge variant where every method raises BridgeError("Test error").
    Used to test error-handling paths.

tmp_config (function scope)
    Patches CONFIG_FILE / CONFIG_DIR to a tmp_path location and writes a
    minimal valid config (app_id, secret, auth_tokens set to non-empty
    strings so the "first launch" dialog does not auto-open).
    Returns the config dict that was written so tests can inspect it.

    Implementation hint:
        Use the same _patch_config_path() helper from tests/test_config.py.

slow_download_mock (function scope)
    A mock_bridge variant where download_track() sleeps for 0.5 s per call
    (using time.sleep inside a side_effect), so tests can verify that the
    cancel button fires before the "download" completes.
    Uses a threading.Event to synchronise with the test thread.
"""

import pytest


# ---------------------------------------------------------------------------
# Skip entire module if PyQt6 is absent
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(items):
    """Auto-skip gui tests when PyQt6 is not installed."""
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        skip = pytest.mark.skip(reason="PyQt6 not installed — run: pip install qobuz-dl[gui]")
        for item in items:
            if "gui" in str(item.fspath):
                item.add_marker(skip)


# ---------------------------------------------------------------------------
# Fixtures (stubs — implement alongside the widgets)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bridge():
    """NOT IMPLEMENTED — returns a plain MagicMock as a placeholder."""
    from unittest.mock import MagicMock
    return MagicMock()


@pytest.fixture
def mock_bridge_error():
    """NOT IMPLEMENTED — returns a MagicMock where every call raises."""
    from unittest.mock import MagicMock
    from qobuz_dl.gui.bridge import BridgeError
    m = MagicMock()
    m.search.side_effect = BridgeError("Simulated API error")
    m.get_album_info.side_effect = BridgeError("Simulated API error")
    m.get_track_info.side_effect = BridgeError("Simulated API error")
    m.download_track.side_effect = BridgeError("Simulated API error")
    return m


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """NOT IMPLEMENTED — patch config paths to tmp_path."""
    raise NotImplementedError(
        "Implement this fixture alongside SetupDialog and load_config integration."
    )
