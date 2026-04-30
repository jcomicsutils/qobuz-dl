"""
tests/test_constants.py — Internal consistency checks on constants.

These tests have no logic of their own — they just assert that the maps
stay in sync with each other as the codebase evolves.
"""

import re
from qobuz_dl.constants import (
    DEFAULT_CONFIG,
    EXT_MAP,
    METADATA_FIELDS,
    QUALITY_LABELS,
    QUALITY_MAP,
    ALBUM_URL_RE,
    TRACK_URL_RE,
    ARTIST_URL_RE,
)


class TestQualityMaps:
    def test_every_quality_key_has_a_label(self):
        """Every human-facing quality name maps to a labelled format ID."""
        for key, qid in QUALITY_MAP.items():
            assert qid in QUALITY_LABELS, (
                f"QUALITY_MAP[{key!r}] = {qid!r} has no entry in QUALITY_LABELS"
            )

    def test_every_quality_key_has_an_extension(self):
        """Every format ID has a known file extension."""
        for key, qid in QUALITY_MAP.items():
            assert qid in EXT_MAP, (
                f"QUALITY_MAP[{key!r}] = {qid!r} has no entry in EXT_MAP"
            )

    def test_ext_map_values_are_known_audio_formats(self):
        known = {"mp3", "flac"}
        for qid, ext in EXT_MAP.items():
            assert ext in known, f"EXT_MAP[{qid!r}] = {ext!r} is not a known audio format"

    def test_mp3_quality_maps_to_mp3_extension(self):
        assert EXT_MAP[QUALITY_MAP["mp3"]] == "mp3"

    def test_cd_and_hires_map_to_flac(self):
        assert EXT_MAP[QUALITY_MAP["cd"]]         == "flac"
        assert EXT_MAP[QUALITY_MAP["hi-res"]]      == "flac"
        assert EXT_MAP[QUALITY_MAP["hi-res-192"]]  == "flac"


class TestMetadataFields:
    def test_all_defaults_are_true(self):
        """Every metadata field should be enabled by default."""
        for field, enabled in METADATA_FIELDS.items():
            assert enabled is True, f"METADATA_FIELDS[{field!r}] defaults to False — intentional?"

    def test_expected_fields_present(self):
        expected = {
            "title", "artist", "album_artist", "album",
            "track_number", "disc_number", "date", "year",
            "genre", "label", "copyright", "isrc", "upc", "cover",
        }
        assert set(METADATA_FIELDS.keys()) == expected


class TestDefaultConfig:
    def test_default_quality_is_in_quality_map(self):
        assert DEFAULT_CONFIG["quality"] in QUALITY_MAP

    def test_default_metadata_fields_match_metadata_fields_constant(self):
        assert DEFAULT_CONFIG["metadata_fields"] == dict(METADATA_FIELDS)

    def test_on_final_failure_is_valid(self):
        valid = {"keep_partial", "delete_partial", "delete_album"}
        assert DEFAULT_CONFIG["on_final_failure"] in valid

    def test_retries_is_non_negative_int(self):
        assert isinstance(DEFAULT_CONFIG["retries"], int)
        assert DEFAULT_CONFIG["retries"] >= 0

    def test_truncate_positions_are_valid(self):
        valid = {"end", "middle"}
        assert DEFAULT_CONFIG["filename_truncate_pos"] in valid
        assert DEFAULT_CONFIG["folder_truncate_pos"]   in valid

    def test_byte_budgets_are_sensible(self):
        assert 16 <= DEFAULT_CONFIG["filename_max_bytes"] <= 255
        assert 16 <= DEFAULT_CONFIG["folder_max_bytes"]   <= 255


class TestUrlRegexes:
    # ── album ─────────────────────────────────────────────────────────────────
    def test_album_url_play_domain(self):
        m = ALBUM_URL_RE.search("https://play.qobuz.com/album/0060253780948")
        assert m and m.group(1) == "0060253780948"

    def test_album_url_open_domain(self):
        m = ALBUM_URL_RE.search("https://open.qobuz.com/album/abc123XYZ")
        assert m and m.group(1) == "abc123XYZ"

    def test_album_url_does_not_match_track(self):
        assert ALBUM_URL_RE.search("https://play.qobuz.com/track/23929921") is None

    # ── track ─────────────────────────────────────────────────────────────────
    def test_track_url_play_domain(self):
        m = TRACK_URL_RE.search("https://play.qobuz.com/track/23929921")
        assert m and m.group(1) == "23929921"

    def test_track_url_open_domain(self):
        m = TRACK_URL_RE.search("https://open.qobuz.com/track/99887766")
        assert m and m.group(1) == "99887766"

    def test_track_url_does_not_match_album(self):
        assert TRACK_URL_RE.search("https://play.qobuz.com/album/0060253780948") is None

    # ── artist ────────────────────────────────────────────────────────────────
    def test_artist_url_play_domain(self):
        m = ARTIST_URL_RE.search("https://play.qobuz.com/artist/707261")
        assert m and m.group(1) == "707261"

    def test_artist_url_open_domain(self):
        m = ARTIST_URL_RE.search("https://open.qobuz.com/artist/5765466")
        assert m and m.group(1) == "5765466"

    def test_artist_url_does_not_match_album(self):
        assert ARTIST_URL_RE.search("https://play.qobuz.com/album/0060253780948") is None

    def test_no_match_on_random_url(self):
        url = "https://www.google.com/search?q=qobuz"
        assert ALBUM_URL_RE.search(url)  is None
        assert TRACK_URL_RE.search(url)  is None
        assert ARTIST_URL_RE.search(url) is None
