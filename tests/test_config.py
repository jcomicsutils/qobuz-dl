"""
tests/test_config.py — Tests for qobuz_dl.config.

Uses tmp_path to avoid touching the real config file on disk.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from qobuz_dl.constants import DEFAULT_CONFIG, METADATA_FIELDS
from qobuz_dl.config import get_meta_fields, load_config, save_config


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _patch_config_path(tmp_path: Path):
    """Context manager that redirects CONFIG_FILE and CONFIG_DIR to tmp_path."""
    fake_dir  = tmp_path / "qobuz-dl"
    fake_file = fake_dir  / "config.json"
    return patch.multiple(
        "qobuz_dl.config",
        CONFIG_DIR  = fake_dir,
        CONFIG_FILE = fake_file,
    )


# ─────────────────────────────────────────────────────────────────────────────
# load_config
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        with _patch_config_path(tmp_path):
            cfg = load_config()
        assert cfg == DEFAULT_CONFIG

    def test_loaded_config_has_all_default_keys(self, tmp_path):
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        fake_dir.mkdir()
        # Write a minimal config — only app_id
        fake_file.write_text(json.dumps({"app_id": "test123"}))
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            cfg = load_config()
        # Every default key must be present
        for key in DEFAULT_CONFIG:
            assert key in cfg, f"Key {key!r} not back-filled from defaults"

    def test_loaded_values_override_defaults(self, tmp_path):
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        fake_dir.mkdir()
        fake_file.write_text(json.dumps({"quality": "cd", "retries": 10}))
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            cfg = load_config()
        assert cfg["quality"]  == "cd"
        assert cfg["retries"]  == 10

    def test_default_values_not_overwritten_by_existing_keys(self, tmp_path):
        """Values present in the file must NOT be overwritten by defaults."""
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        fake_dir.mkdir()
        fake_file.write_text(json.dumps({"save_cover": False}))
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            cfg = load_config()
        assert cfg["save_cover"] is False   # must not be reset to True


# ─────────────────────────────────────────────────────────────────────────────
# save_config
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveConfig:
    def test_creates_directory_and_file(self, tmp_path):
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            save_config({"quality": "cd"})
        assert fake_file.exists()

    def test_written_json_is_readable(self, tmp_path):
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        payload   = {"quality": "cd", "retries": 5}
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            save_config(payload)
        loaded = json.loads(fake_file.read_text())
        assert loaded == payload

    def test_roundtrip(self, tmp_path):
        fake_dir  = tmp_path / "qobuz-dl"
        fake_file = fake_dir  / "config.json"
        original  = {**DEFAULT_CONFIG, "quality": "mp3", "retries": 7}
        with patch.multiple("qobuz_dl.config", CONFIG_DIR=fake_dir, CONFIG_FILE=fake_file):
            save_config(original)
            loaded = load_config()
        assert loaded["quality"] == "mp3"
        assert loaded["retries"] == 7


# ─────────────────────────────────────────────────────────────────────────────
# get_meta_fields
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMetaFields:
    def test_returns_none_when_embed_disabled(self):
        cfg = {**DEFAULT_CONFIG, "embed_metadata": False}
        assert get_meta_fields(cfg) is None

    def test_returns_dict_when_embed_enabled(self):
        cfg = {**DEFAULT_CONFIG, "embed_metadata": True}
        result = get_meta_fields(cfg)
        assert isinstance(result, dict)

    def test_all_fields_enabled_by_default(self):
        cfg = {**DEFAULT_CONFIG, "embed_metadata": True, "metadata_fields": {}}
        result = get_meta_fields(cfg)
        # With no overrides, every METADATA_FIELDS entry should be True
        for field, default_val in METADATA_FIELDS.items():
            assert result[field] == default_val

    def test_stored_fields_override_defaults(self):
        cfg = {
            **DEFAULT_CONFIG,
            "embed_metadata": True,
            "metadata_fields": {"cover": False, "isrc": False},
        }
        result = get_meta_fields(cfg)
        assert result["cover"] is False
        assert result["isrc"]  is False

    def test_fields_not_in_stored_config_default_to_true(self):
        """Simulate an old config file that predates a new metadata field."""
        # Suppose "label" was added after the user ran setup — it's absent from their file.
        stored = {k: True for k in METADATA_FIELDS if k != "label"}
        cfg    = {**DEFAULT_CONFIG, "embed_metadata": True, "metadata_fields": stored}
        result = get_meta_fields(cfg)
        # "label" is in METADATA_FIELDS (defaults True), so it must be True here too
        assert result["label"] is True

    def test_no_metadata_fields_key_uses_all_defaults(self):
        cfg = {**DEFAULT_CONFIG, "embed_metadata": True}
        cfg.pop("metadata_fields", None)
        result = get_meta_fields(cfg)
        assert result == dict(METADATA_FIELDS)
