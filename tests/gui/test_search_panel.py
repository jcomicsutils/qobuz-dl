"""
tests/gui/test_search_panel.py — Tests for SearchPanel.

NOT IMPLEMENTED — test bodies are stubs showing what each test must verify.

All tests require pytest-qt (`qtbot` fixture) and a working SearchPanel.
"""

import pytest

pytestmark = pytest.mark.gui


class TestSearchPanelInput:
    """Tests for the search bar interaction."""

    def test_enter_key_triggers_search(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Type a query into the search box and press Enter.
          mock_bridge.search must be called with that query string.

        HOW:
          from qobuz_dl.gui.widgets.search_panel import SearchPanel
          panel = SearchPanel(mock_bridge)
          qtbot.addWidget(panel)
          qtbot.keyClicks(panel.search_box, "Autechre")
          qtbot.keyPress(panel.search_box, Qt.Key.Key_Return)
          # Because SearchWorker runs on QThreadPool, wait for signal:
          with qtbot.waitSignal(panel._search_done, timeout=2000):
              pass
          mock_bridge.search.assert_called_once_with("Autechre", ...)
        """
        raise NotImplementedError

    def test_go_button_triggers_search(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Same as above but click the [Go] button instead of pressing Enter.
        """
        raise NotImplementedError

    def test_empty_query_does_not_trigger_search(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Click [Go] with an empty search box.  mock_bridge.search must not
          be called, and no error dialog must appear.
        """
        raise NotImplementedError

    def test_type_filter_passed_to_bridge(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Select "Tracks" in the type dropdown.  After a search,
          mock_bridge.search must be called with search_type="tracks"
          (or however Bridge maps the UI value).
        """
        raise NotImplementedError


class TestSearchPanelResults:
    """Tests for results table population."""

    def test_album_results_populate_table(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.search returns two AlbumInfo items.  After the
          worker completes, the albums table must have exactly 2 rows,
          with correct artist and title text in the right columns.
        """
        raise NotImplementedError

    def test_empty_results_hides_tables(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.search returns an empty SearchResult.  The result
          tables (or their section headers) must not be visible, and a
          "No results found" message must appear somewhere.
        """
        raise NotImplementedError

    def test_previous_results_cleared_on_new_search(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Do a search that returns 3 albums.  Then do another search that
          returns 1 album.  The table must show only 1 row — stale rows
          from the first search must be gone.
        """
        raise NotImplementedError

    def test_search_error_shows_message_box(self, qtbot, mock_bridge_error):
        """
        WHAT TO VERIFY:
          mock_bridge.search raises BridgeError.  A QMessageBox.warning
          must appear with the error text.  The panel must not crash.

        HOW (intercept the dialog before it blocks):
          Use qtbot.waitSignal or monkeypatch QMessageBox.warning to
          capture the call without showing a real dialog.
        """
        raise NotImplementedError

    def test_go_button_disabled_during_search(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          While the SearchWorker is running (before results_ready fires),
          the [Go] button must be disabled so the user cannot stack searches.
          After results arrive, it must be re-enabled.
        """
        raise NotImplementedError


class TestSearchPanelActions:
    """Tests for row interactions."""

    def test_double_click_album_row_emits_download_requested(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          After a search with one album result, double-click the row.
          SearchPanel.download_requested must be emitted with a Qobuz
          album URL string.

        HOW:
          with qtbot.waitSignal(panel.download_requested, timeout=1000) as sig:
              qtbot.mouseDClick(panel.albums_table.viewport(), Qt.LeftButton,
                                pos=panel.albums_table.visualItemRect(...).center())
          assert "qobuz.com/album" in sig.args[0]
        """
        raise NotImplementedError

    def test_double_click_track_row_emits_download_requested(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Same as above but for the tracks table.  Emitted URL contains
          "qobuz.com/track".
        """
        raise NotImplementedError

    def test_right_click_shows_context_menu(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Right-clicking a result row shows a context menu.  The menu must
          contain at least "Download" and "Copy URL" actions.
        """
        raise NotImplementedError

    def test_copy_url_puts_url_on_clipboard(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Click "Copy URL" from the context menu.  QApplication.clipboard().text()
          must equal the Qobuz URL for that row.
        """
        raise NotImplementedError
