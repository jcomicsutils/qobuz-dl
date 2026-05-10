"""
tests/gui/test_workers.py — Tests for SearchWorker and DownloadWorker.

NOT IMPLEMENTED — test bodies are stubs showing what each test must verify.

Workers are QRunnables — they have no GUI and can be tested with minimal
Qt involvement.  Most tests here spin up a QApplication (required for signals)
but do not open any windows.

All tests require pytest-qt.
"""

import pytest
import threading

pytestmark = pytest.mark.gui


class TestSearchWorker:
    """Unit tests for SearchWorker."""

    def test_emits_results_ready_on_success(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Construct a SearchWorker with mock_bridge and run it.
          signals.results_ready must be emitted with a SearchResult object.

        HOW:
          from qobuz_dl.gui.workers.search_worker import SearchWorker
          worker = SearchWorker(mock_bridge, "Autechre", 10, "all")
          with qtbot.waitSignal(worker.signals.results_ready, timeout=2000) as sig:
              worker.run()   # run synchronously in the test thread
          assert sig.args[0].albums is not None
        """
        raise NotImplementedError

    def test_emits_error_on_bridge_error(self, qtbot, mock_bridge_error):
        """
        WHAT TO VERIFY:
          mock_bridge_error.search raises BridgeError.
          signals.error must be emitted with the error message string.
          signals.results_ready must NOT be emitted.
        """
        raise NotImplementedError

    def test_passes_query_and_limit_to_bridge(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          After run(), mock_bridge.search must have been called with exactly
          the query, limit, and search_type that were passed to the constructor.
        """
        raise NotImplementedError

    def test_does_not_touch_widgets(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          run() must not call any QWidget methods.  One way: monkeypatch
          QWidget.__init__ to raise, and confirm that run() completes without
          triggering it.  Another way: inspect that no QWidget subclass is
          instantiated during the run.

        WHY THIS MATTERS:
          Creating or modifying QWidgets from a non-main thread causes
          crashes or silent corruption that are very hard to debug.
        """
        raise NotImplementedError


class TestDownloadWorker:
    """Unit tests for DownloadWorker."""

    def test_emits_finished_true_on_success(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.download_track returns True for all tracks.
          signals.finished must be emitted with True.
        """
        raise NotImplementedError

    def test_emits_finished_false_on_failure(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.download_track returns False for at least one track.
          signals.finished must be emitted with False.
        """
        raise NotImplementedError

    def test_emits_track_started_per_track(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.get_album_info returns an AlbumInfo with 3 tracks.
          signals.track_started must be emitted exactly 3 times.

        HOW:
          Connect track_started to a counter list:
            received = []
            worker.signals.track_started.connect(lambda *args: received.append(args))
            worker.run()
            assert len(received) == 3
        """
        raise NotImplementedError

    def test_cancel_event_stops_loop_between_tracks(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.get_album_info returns an album with 3 tracks.
          Set cancel_event before run() starts.
          mock_bridge.download_track must be called 0 times (cancelled before
          the first track begins).
          signals.finished must still be emitted with False.

        WHY:
          This verifies the between-track cancellation check described in
          download_worker.py.  The within-chunk cancellation is tested
          separately in tests for stream_download (core, not GUI).
        """
        raise NotImplementedError

    def test_progress_signal_forwarded_from_callback(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.download_track calls its on_progress callback with
          (512, 1024) during the call.  The worker must forward this by
          emitting signals.progress(512, 1024).

        HOW:
          Use a side_effect on mock_bridge.download_track that calls
          the on_progress kwarg:

              def fake_download(*args, on_progress=None, **kwargs):
                  if on_progress:
                      on_progress(512, 1024)
                  return True
              mock_bridge.download_track.side_effect = fake_download

          Then assert signals.progress was emitted with (512, 1024).
        """
        raise NotImplementedError

    def test_error_signal_emitted_on_bridge_error_before_download(self, qtbot, mock_bridge_error):
        """
        WHAT TO VERIFY:
          mock_bridge_error.get_album_info raises BridgeError.
          signals.error must be emitted with the message string.
          signals.finished must NOT be emitted (nothing to finish).
        """
        raise NotImplementedError

    def test_worker_run_is_not_on_main_thread(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          Submit the worker to QThreadPool.globalInstance() (not call run()
          directly).  Inside mock_bridge.download_track.side_effect, record
          threading.current_thread().ident.  After the worker finishes
          (wait on signals.finished), assert the recorded ident is not
          threading.main_thread().ident.

        WHY:
          This is the most important test in this file.  If the download
          blocks the main thread, the UI freezes.
        """
        raise NotImplementedError
