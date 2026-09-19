"""
tests/test_batch_dl.py — Unit tests for batch downloads and separator flags.
"""

from unittest.mock import MagicMock, patch
import click
from click.testing import CliRunner
import pytest

from qobuz_dl.cli.dl import (
    SEPARATORS,
    BatchDlCommand,
    _run_download_group,
    dl,
    split_groups,
)


# ─────────────────────────────────────────────────────────────────────────────
# split_groups
# ─────────────────────────────────────────────────────────────────────────────

class TestSplitGroups:
    def test_single_group_no_separators(self):
        args = ["ar-id", "1", "2", "-a", "artist1"]
        result = split_groups(args)
        assert result == [["ar-id", "1", "2", "-a", "artist1"]]

    def test_split_by_next(self):
        args = ["ar-id", "1", "2", "-a", "artist1", "--next", "ar-id", "3", "-a", "artist2"]
        result = split_groups(args)
        assert result == [
            ["ar-id", "1", "2", "-a", "artist1"],
            ["ar-id", "3", "-a", "artist2"],
        ]

    def test_split_by_plus(self):
        args = ["ar-id", "1", "2", "-a", "artist1", "+", "ar-id", "3", "-a", "artist2"]
        result = split_groups(args)
        assert result == [
            ["ar-id", "1", "2", "-a", "artist1"],
            ["ar-id", "3", "-a", "artist2"],
        ]

    def test_split_by_and(self):
        args = ["ar-id", "1", "2", "-a", "artist1", "--and", "ar-id", "3", "-a", "artist2"]
        result = split_groups(args)
        assert result == [
            ["ar-id", "1", "2", "-a", "artist1"],
            ["ar-id", "3", "-a", "artist2"],
        ]

    def test_multiple_groups(self):
        args = ["ar-id", "1", "+", "ar-id", "2", "--next", "ar-id", "3"]
        result = split_groups(args)
        assert len(result) == 3
        assert result[0] == ["ar-id", "1"]
        assert result[1] == ["ar-id", "2"]
        assert result[2] == ["ar-id", "3"]

    def test_leading_separator_raises(self):
        with pytest.raises(click.ClickException, match="Empty target group before separator"):
            split_groups(["--next", "ar-id", "1"])

    def test_trailing_separator_raises(self):
        with pytest.raises(click.ClickException, match="Trailing separator"):
            split_groups(["ar-id", "1", "+"])

    def test_consecutive_separators_raises(self):
        with pytest.raises(click.ClickException, match="Empty target group between consecutive separators"):
            split_groups(["ar-id", "1", "+", "+", "ar-id", "2"])

    def test_multiple_artist_overrides_without_separator_raises(self):
        with pytest.raises(click.ClickException, match="Multiple -a / --override-main-artist flags detected"):
            split_groups(["ar-id", "1", "-a", "artist1", "ar-id", "2", "-a", "artist2"])

    def test_multiple_artist_overrides_long_flag_without_separator_raises(self):
        with pytest.raises(click.ClickException, match="Multiple -a / --override-main-artist flags detected"):
            split_groups(["ar-id", "1", "--override-main-artist=artist1", "ar-id", "2", "--override-main-artist", "artist2"])


# ─────────────────────────────────────────────────────────────────────────────
# BatchDlCommand parsing and option inheritance
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchDlCommand:
    def test_help_mentions_separators_and_multi_page(self):
        runner = CliRunner()
        res = runner.invoke(dl, ["--help"])
        assert res.exit_code == 0
        assert "--next" in res.output
        assert "Multiple pages for the same artist" in res.output
        assert "Batch downloads & multiple artists" in res.output

    @patch("qobuz_dl.cli.dl._run_download_group")
    @patch("qobuz_dl.cli.dl.QobuzAPI")
    @patch("qobuz_dl.cli.dl.load_config")
    def test_single_group_multi_page_artist(self, mock_cfg, mock_api, mock_run):
        mock_cfg.return_value = {"quality": "hi-res-192", "download_dir": "/tmp"}
        runner = CliRunner()
        res = runner.invoke(dl, ["ar-id", "1", "2", "-a", "Artist 1", "--dry-run"])
        assert res.exit_code == 0
        assert mock_run.call_count == 1
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["targets"] == [("artist", "1"), ("artist", "2")]
        assert call_kwargs["override_main_artist"] == "Artist 1"
        assert call_kwargs["dry_run"] is True

    @patch("qobuz_dl.cli.dl._run_download_group")
    @patch("qobuz_dl.cli.dl.QobuzAPI")
    @patch("qobuz_dl.cli.dl.load_config")
    def test_multiple_groups_option_inheritance(self, mock_cfg, mock_api, mock_run):
        mock_cfg.return_value = {"quality": "hi-res-192", "download_dir": "/tmp"}
        runner = CliRunner()
        res = runner.invoke(dl, [
            "-q", "cd", "--dry-run", "ar-id", "1", "2", "-a", "Artist 1",
            "+",
            "ar-id", "3", "-a", "Artist 2",
        ])
        assert res.exit_code == 0
        assert mock_run.call_count == 2

        # Group 1
        g1 = mock_run.call_args_list[0][1]
        assert g1["targets"] == [("artist", "1"), ("artist", "2")]
        assert g1["override_main_artist"] == "Artist 1"
        assert g1["quality_id"] == "6"  # cd -> 6
        assert g1["dry_run"] is True

        # Group 2 (inherited quality and dry_run, distinct artist override)
        g2 = mock_run.call_args_list[1][1]
        assert g2["targets"] == [("artist", "3")]
        assert g2["override_main_artist"] == "Artist 2"
        assert g2["quality_id"] == "6"  # inherited cd
        assert g2["dry_run"] is True

    @patch("qobuz_dl.cli.dl._run_download_group")
    @patch("qobuz_dl.cli.dl.QobuzAPI")
    @patch("qobuz_dl.cli.dl.load_config")
    def test_group_can_override_inherited_quality(self, mock_cfg, mock_api, mock_run):
        mock_cfg.return_value = {"quality": "hi-res-192", "download_dir": "/tmp"}
        runner = CliRunner()
        res = runner.invoke(dl, [
            "-q", "cd", "ar-id", "1", "-a", "Artist 1",
            "--next",
            "-q", "mp3", "ar-id", "2", "-a", "Artist 2",
        ])
        assert res.exit_code == 0
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][1]["quality_id"] == "6"  # cd
        assert mock_run.call_args_list[1][1]["quality_id"] == "5"  # mp3

    @patch("qobuz_dl.cli.dl._run_download_group")
    @patch("qobuz_dl.cli.dl.QobuzAPI")
    @patch("qobuz_dl.cli.dl.load_config")
    def test_group_without_artist_override_does_not_leak_previous_override(self, mock_cfg, mock_api, mock_run):
        mock_cfg.return_value = {"quality": "hi-res-192", "download_dir": "/tmp"}
        runner = CliRunner()
        res = runner.invoke(dl, [
            "ar-id", "1", "-a", "Artist 1",
            "+",
            "ar-id", "2",
        ])
        assert res.exit_code == 0
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][1]["override_main_artist"] == "Artist 1"
        assert mock_run.call_args_list[1][1]["override_main_artist"] is None


# ─────────────────────────────────────────────────────────────────────────────
# _run_download_group artist ID unification
# ─────────────────────────────────────────────────────────────────────────────

class TestRunDownloadGroupMultiPage:
    @patch("qobuz_dl.cli.dl.dry_run_album")
    def test_multi_page_artist_unifies_under_first_artist_id(self, mock_dry_album):
        mock_api = MagicMock()
        mock_api.get_artist_releases.side_effect = [
            {"items": [{"id": "alb1"}], "has_more": False},
            {"items": [], "has_more": False},
            {"items": [], "has_more": False},
            {"items": [], "has_more": False},
            {"items": [{"id": "alb2"}], "has_more": False},
            {"items": [], "has_more": False},
            {"items": [], "has_more": False},
            {"items": [], "has_more": False},
        ]
        targets = [("artist", "100"), ("artist", "200")]
        from pathlib import Path
        _run_download_group(
            api=mock_api,
            targets=targets,
            effective_cfg={},
            quality_id="27",
            root_dir=Path("/tmp"),
            f_tmpl="{artist}/{album}",
            t_tmpl="{title}",
            dry_run=True,
            override_main_artist="Unified Artist",
            override_artist_id=False,
        )

        assert mock_dry_album.call_count == 2
        # Verify both calls used global_artist_id="100" (first artist ID) and override_main_artist="Unified Artist"
        call1 = mock_dry_album.call_args_list[0]
        assert call1[0][1] == "alb1"
        assert call1[0][7] == "Unified Artist"  # override_main_artist
        assert call1[0][8] == "100"             # global_artist_id

        call2 = mock_dry_album.call_args_list[1]
        assert call2[0][1] == "alb2"
        assert call2[0][7] == "Unified Artist"  # override_main_artist
        assert call2[0][8] == "100"             # global_artist_id


# ─────────────────────────────────────────────────────────────────────────────
# Shell tab completion after separators
# ─────────────────────────────────────────────────────────────────────────────

class TestShellCompletionAfterSeparator:
    def test_completion_after_plus_separator(self):
        from click.shell_completion import ShellComplete
        from qobuz_dl.cli import cli

        comp = ShellComplete(cli, {}, "qobuz-dl", "_QOBUZ_DL_COMPLETE")
        items = comp.get_completions(["dl", "ar-id", "2746522", "-a", "Cages", "+"], "ar")
        values = [i.value for i in items]
        assert "ar-id" in values

    def test_completion_after_next_separator(self):
        from click.shell_completion import ShellComplete
        from qobuz_dl.cli import cli

        comp = ShellComplete(cli, {}, "qobuz-dl", "_QOBUZ_DL_COMPLETE")
        items = comp.get_completions(["dl", "ar-id", "2746522", "-a", "Cages", "--next"], "ar")
        values = [i.value for i in items]
        assert "ar-id" in values

    def test_completion_empty_incomplete_after_separator(self):
        from click.shell_completion import ShellComplete
        from qobuz_dl.cli import cli

        comp = ShellComplete(cli, {}, "qobuz-dl", "_QOBUZ_DL_COMPLETE")
        items = comp.get_completions(["dl", "ar-id", "2746522", "-a", "Cages", "+"], "")
        values = [i.value for i in items]
        assert "ar-id" in values
        assert "al-id" in values
        assert "tr-id" in values


