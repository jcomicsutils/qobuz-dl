"""
tests/gui/test_setup_dialog.py — Tests for SetupDialog.

NOT IMPLEMENTED — test bodies are stubs showing what each test must verify.

All tests require pytest-qt (the `qtbot` fixture) and a working SetupDialog.
Skip this file entirely on machines without PyQt6 (handled by conftest.py).

How to run once implemented:
    pytest tests/gui/test_setup_dialog.py -v
"""

import pytest

pytestmark = pytest.mark.gui


class TestSetupDialogLoading:
    """Tests that the dialog correctly pre-populates from saved config."""

    def test_credentials_pre_populated_from_config(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          Open SetupDialog when the config already contains app_id, secret,
          and an auth token.  The corresponding QLineEdit / QPlainTextEdit
          fields must show those values without the user doing anything.

        HOW:
          from qobuz_dl.gui.windows.setup_dialog import SetupDialog
          dlg = SetupDialog()
          qtbot.addWidget(dlg)
          assert dlg.app_id_field.text() == tmp_config["app_id"]
          assert dlg.secret_field.text() == tmp_config["secret"]
          assert tmp_config["auth_tokens"][0] in dlg.tokens_field.toPlainText()
        """
        raise NotImplementedError

    def test_quality_dropdown_preselects_saved_value(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          The quality QComboBox shows the value stored in config["quality"],
          not always the first item in the list.
        """
        raise NotImplementedError

    def test_all_metadata_checkboxes_reflect_config(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          For each key in METADATA_FIELDS, the corresponding QCheckBox
          initial state (checked/unchecked) matches config["metadata_fields"][key].
          Test with a config where some fields are False.
        """
        raise NotImplementedError

    def test_fallback_path_widget_reflects_config(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          The fallback path list/widget shows the quality keys from
          config["quality_fallback_path"] in the correct order.
        """
        raise NotImplementedError


class TestSetupDialogValidation:
    """Tests that invalid input is caught before saving."""

    def test_save_disabled_when_app_id_empty(self, qtbot):
        """
        WHAT TO VERIFY:
          Clear the App ID field.  The Save / OK button must become disabled
          (or clicking it must show an inline error — whichever design is used).
        """
        raise NotImplementedError

    def test_save_disabled_when_no_auth_tokens(self, qtbot):
        """
        WHAT TO VERIFY:
          Clear all auth tokens.  Save must not proceed.
        """
        raise NotImplementedError

    def test_invalid_folder_template_shows_warning(self, qtbot):
        """
        WHAT TO VERIFY:
          Enter a folder template with an unknown placeholder, e.g.
          "{nonexistent_var}/{album}".  An inline warning label must appear.
          The dialog must not crash.

        WHY:
          safe_format() raises ClickException on unknown keys; the GUI must
          catch this and show it gracefully.
        """
        raise NotImplementedError

    def test_non_integer_retries_rejected(self, qtbot):
        """
        WHAT TO VERIFY:
          If the retries field is a QSpinBox this is guaranteed by the widget;
          if it is a QLineEdit, entering "abc" must show a validation error and
          block Save.
        """
        raise NotImplementedError


class TestSetupDialogSaving:
    """Tests that accepted dialog values are written to disk correctly."""

    def test_save_writes_app_id_to_config(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          Change the App ID field to "new_app_id", click Save, then call
          load_config() and assert config["app_id"] == "new_app_id".
        """
        raise NotImplementedError

    def test_cancel_does_not_write_to_disk(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          Change the App ID field, click Cancel.  load_config() must still
          return the original value — the file must be unchanged.
        """
        raise NotImplementedError

    def test_save_emits_accepted_signal(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          Clicking Save emits the QDialog.accepted signal (or the dialog
          closes with result code QDialog.DialogCode.Accepted).

        HOW (using qtbot.waitSignal):
          with qtbot.waitSignal(dlg.accepted, timeout=1000):
              qtbot.mouseClick(dlg.save_button, Qt.MouseButton.LeftButton)
        """
        raise NotImplementedError

    def test_metadata_field_toggle_persisted(self, qtbot, tmp_config):
        """
        WHAT TO VERIFY:
          Uncheck the "copyright" checkbox, save.  load_config() must show
          config["metadata_fields"]["copyright"] == False.
        """
        raise NotImplementedError


class TestSetupDialogConnectionTest:
    """Tests for the [Test connection] button."""

    def test_successful_connection_shows_green_indicator(self, qtbot, mock_bridge):
        """
        WHAT TO VERIFY:
          mock_bridge.search returns a non-empty result.  Clicking
          [Test connection] sets some indicator widget to a green/success state.
        """
        raise NotImplementedError

    def test_failed_connection_shows_error_message(self, qtbot, mock_bridge_error):
        """
        WHAT TO VERIFY:
          mock_bridge.search raises BridgeError.  Clicking [Test connection]
          shows the error message inline (not a crash).
        """
        raise NotImplementedError
