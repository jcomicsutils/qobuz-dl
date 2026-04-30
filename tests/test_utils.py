"""
tests/test_utils.py — Tests for qobuz_dl.utils.

Covers every public function.  No network calls, no file I/O, no credentials.
"""

import pytest
import click
from unittest.mock import patch

import qobuz_dl.utils
from qobuz_dl.utils import (
    _truncate_bytes,
    _utf8_leading_len,
    _utf8_trailing_len,
    apply_version_to_title,
    clean_name,
    format_bytes,
    get_artists,
    get_main_artist,
    get_quality_tag,
    get_year,
    parse_targets,
    resolve_url,
    safe_format,
    strip_feat_from_album_title,
    strip_feat_from_track_title,
    truncate_name,
    dbg,
    _track_has_featured_artist,
)

class TestDebugLogging:
    @patch("qobuz_dl.utils.console.print")
    def test_dbg_silent_when_verbose_false(self, mock_print):
        qobuz_dl.utils._VERBOSE = False
        dbg("Test message")
        mock_print.assert_not_called()

    @patch("qobuz_dl.utils.console.print")
    def test_dbg_prints_when_verbose_true(self, mock_print):
        qobuz_dl.utils._VERBOSE = True
        dbg("Test message")
        mock_print.assert_called_once_with("[dim][DEBUG][/dim] Test message")
        qobuz_dl.utils._VERBOSE = False

# ─────────────────────────────────────────────────────────────────────────────
# clean_name
# ─────────────────────────────────────────────────────────────────────────────
class TestCleanName:
    def test_replaces_forward_slash(self):
        assert clean_name("AC/DC") == "AC_DC"

    def test_replaces_backslash(self):
        assert clean_name("AC\\DC") == "AC_DC"

    def test_replaces_colon(self):
        assert clean_name("Side A: Part 1") == "Side A_ Part 1"

    def test_replaces_all_illegal_chars(self):
        # Every character in ILLEGAL_CHARS  /\?:*"<>|
        assert "_" not in r'/\?:*"<>|'          # sanity: _ itself is safe
        result = clean_name(r'/\?:*"<>|')
        assert result == "_________"

    def test_strips_trailing_dots(self):
        assert clean_name("name...") == "name"

    def test_strips_leading_and_trailing_spaces(self):
        assert clean_name("  hello  ") == "hello"

    def test_strips_trailing_dot_and_space(self):
        assert clean_name("hello . ") == "hello"

    def test_plain_name_unchanged(self):
        assert clean_name("Autechre") == "Autechre"

    def test_unicode_name_unchanged(self):
        assert clean_name("Sigur Rós") == "Sigur Rós"

    def test_empty_string(self):
        assert clean_name("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# _utf8_trailing_len / _utf8_leading_len
# ─────────────────────────────────────────────────────────────────────────────

class TestUtf8BoundaryHelpers:
    # trailing
    def test_trailing_ascii_is_zero(self):
        assert _utf8_trailing_len(b"hello") == 0

    def test_trailing_complete_2byte_is_zero(self):
        # é = 0xC3 0xA9 — complete sequence
        assert _utf8_trailing_len("é".encode()) == 0

    def test_trailing_incomplete_2byte(self):
        # first byte of é (0xC3) alone — must strip 1
        assert _utf8_trailing_len(b"\xc3") == 1

    def test_trailing_incomplete_3byte_one_continuation(self):
        # First two bytes of a 3-byte char (e.g. 0xE2 0x80) — strip 2
        assert _utf8_trailing_len(b"\xe2\x80") == 2

    def test_trailing_incomplete_3byte_lead_only(self):
        # Just the lead byte 0xE2 — strip 1
        assert _utf8_trailing_len(b"\xe2") == 1

    def test_trailing_empty_bytes(self):
        assert _utf8_trailing_len(b"") == 0

    # leading
    def test_leading_ascii_is_zero(self):
        assert _utf8_leading_len(b"hello") == 0

    def test_leading_continuation_bytes_stripped(self):
        # 0x80 and 0xBF are both continuation bytes (10xxxxxx)
        assert _utf8_leading_len(b"\x80\xbf" + b"ok") == 2

    def test_leading_no_continuation(self):
        # 0xC3 is a lead byte (110xxxxx), not a continuation
        assert _utf8_leading_len(b"\xc3\xa9rest") == 0

    def test_leading_empty_bytes(self):
        assert _utf8_leading_len(b"") == 0


# ─────────────────────────────────────────────────────────────────────────────
# _truncate_bytes
# ─────────────────────────────────────────────────────────────────────────────

class TestTruncateBytes:
    def test_short_string_unchanged(self):
        assert _truncate_bytes("hello", 20, "end", "...") == "hello"

    def test_exact_length_unchanged(self):
        text = "hello"
        assert _truncate_bytes(text, len(text.encode()), "end", "") == text

    def test_end_truncation_within_budget(self):
        result = _truncate_bytes("abcdefghij", 5, "end", "")
        assert len(result.encode()) <= 5

    def test_end_truncation_with_marker(self):
        result = _truncate_bytes("abcdefghij", 6, "end", "...")
        assert len(result.encode()) <= 6
        assert result.endswith("...")

    def test_middle_truncation_within_budget(self):
        result = _truncate_bytes("abcdefghij", 7, "middle", "-")
        assert len(result.encode()) <= 7
        assert "-" in result

    def test_result_is_valid_utf8(self):
        # CJK characters are 3 bytes each — verify no split sequences
        cjk = "日本語テスト音楽"
        for max_b in range(1, len(cjk.encode()) + 1):
            result = _truncate_bytes(cjk, max_b, "end", "")
            result.encode("utf-8")   # raises UnicodeEncodeError if broken

    def test_middle_result_is_valid_utf8(self):
        cjk = "日本語テスト音楽"
        for max_b in range(1, len(cjk.encode()) + 1):
            result = _truncate_bytes(cjk, max_b, "middle", "…")
            result.encode("utf-8")

    def test_marker_larger_than_budget_returns_clipped_marker(self):
        # marker "..." is 3 bytes, budget is 2 — should return at most 2 bytes of marker
        result = _truncate_bytes("hello world", 2, "end", "...")
        assert len(result.encode()) <= 2

    def test_end_no_marker(self):
        result = _truncate_bytes("hello world", 5, "end", "")
        assert result == "hello"

    def test_middle_symmetric_split(self):
        # "abcdefghij" → "ab-ij" with budget=5, marker="-"
        result = _truncate_bytes("abcdefghij", 5, "middle", "-")
        assert len(result.encode()) <= 5
        assert result.startswith("ab")
        assert result.endswith("ij")


# ─────────────────────────────────────────────────────────────────────────────
# truncate_name
# ─────────────────────────────────────────────────────────────────────────────

class TestTruncateName:
    BASE_CFG = {
        "truncate_filename":        True,
        "filename_truncate_pos":    "end",
        "filename_truncate_marker": "...",
        "filename_max_bytes":       20,
        "truncate_folder":          True,
        "folder_truncate_pos":      "end",
        "folder_truncate_marker":   "",
        "folder_max_bytes":         20,
    }

    def test_filename_short_unchanged(self):
        assert truncate_name("short.flac", self.BASE_CFG, "filename") == "short.flac"

    def test_filename_extension_preserved(self):
        long_stem = "a" * 50
        result = truncate_name(f"{long_stem}.flac", self.BASE_CFG, "filename")
        assert result.endswith(".flac")

    def test_filename_within_byte_budget(self):
        long_name = "a" * 50 + ".flac"
        result = truncate_name(long_name, self.BASE_CFG, "filename")
        assert len(result.encode()) <= 20

    def test_filename_disabled_returns_unchanged(self):
        cfg = {**self.BASE_CFG, "truncate_filename": False}
        long_name = "a" * 300 + ".flac"
        assert truncate_name(long_name, cfg, "filename") == long_name

    def test_folder_short_unchanged(self):
        assert truncate_name("short", self.BASE_CFG, "folder") == "short"

    def test_folder_within_byte_budget(self):
        long_name = "a" * 50
        result = truncate_name(long_name, self.BASE_CFG, "folder")
        assert len(result.encode()) <= 20

    def test_folder_disabled_returns_unchanged(self):
        cfg = {**self.BASE_CFG, "truncate_folder": False}
        long_name = "a" * 300
        assert truncate_name(long_name, cfg, "folder") == long_name

    def test_filename_no_dot_treats_whole_name_as_stem(self):
        long_name = "a" * 50
        result = truncate_name(long_name, self.BASE_CFG, "filename")
        assert len(result.encode()) <= 20

    def test_filename_middle_truncation(self):
        cfg = {**self.BASE_CFG, "filename_truncate_pos": "middle", "filename_truncate_marker": "-"}
        result = truncate_name("abcdefghij_stem.flac", cfg, "filename")
        assert result.endswith(".flac")
        assert len(result.encode()) <= 20


# ─────────────────────────────────────────────────────────────────────────────
# safe_format
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeFormat:
    def test_basic_substitution(self):
        result = safe_format("{artist}/{album}", artist="Aphex Twin", album="Selected")
        assert result == "Aphex Twin/Selected"

    def test_illegal_chars_sanitised_in_values(self):
        result = safe_format("{title}", title="Side A: Part 1")
        assert ":" not in result
        assert result == "Side A_ Part 1"

    def test_integer_values_not_sanitised(self):
        result = safe_format("{track:02d}", track=3)
        assert result == "03"

    def test_missing_key_raises_click_exception(self):
        with pytest.raises(click.ClickException, match="Template error"):
            safe_format("{missing_key}", artist="test")

    def test_unicode_values_preserved_after_clean(self):
        result = safe_format("{artist}", artist="Sigur Rós")
        assert result == "Sigur Rós"

    def test_multiple_variables(self):
        result = safe_format("{artist} - {album} ({year})", artist="A", album="B", year="2020")
        assert result == "A - B (2020)"


# ─────────────────────────────────────────────────────────────────────────────
# format_bytes
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(512) == "512.0 B"

    def test_kilobytes(self):
        assert format_bytes(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_bytes(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_bytes(1024 ** 3) == "1.0 GB"

    def test_terabytes(self):
        assert format_bytes(1024 ** 4) == "1.0 TB"

    def test_fractional(self):
        assert format_bytes(1536) == "1.5 KB"


# ─────────────────────────────────────────────────────────────────────────────
# get_artists / get_main_artist
# ─────────────────────────────────────────────────────────────────────────────

class TestGetArtists:
    def test_multiple_artists_joined(self):
        album = {"artists": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
        assert get_artists(album) == "A, B, C"

    def test_single_artist_in_artists_list(self):
        album = {"artists": [{"name": "Autechre"}]}
        assert get_artists(album) == "Autechre"

    def test_fallback_to_artist_name(self):
        album = {"artist": {"name": "Burial"}}
        assert get_artists(album) == "Burial"

    def test_fallback_to_various_artists(self):
        assert get_artists({}) == "Various Artists"

    def test_empty_artists_list_falls_back(self):
        album = {"artists": [], "artist": {"name": "Burial"}}
        assert get_artists(album) == "Burial"


class TestGetMainArtist:
    def test_returns_artist_name(self):
        album = {"artist": {"name": "Burial"}}
        assert get_main_artist(album) == "Burial"

    def test_fallback_to_unknown(self):
        assert get_main_artist({}) == "Unknown Artist"

    def test_ignores_artists_list(self):
        # get_main_artist should only look at the primary "artist" key
        album = {"artists": [{"name": "A"}, {"name": "B"}], "artist": {"name": "A"}}
        assert get_main_artist(album) == "A"


# ─────────────────────────────────────────────────────────────────────────────
# get_year
# ─────────────────────────────────────────────────────────────────────────────

class TestGetYear:
    def test_extracts_year_from_full_date(self):
        assert get_year({"release_date_original": "2003-09-29"}) == "2003"

    def test_extracts_year_from_year_only(self):
        assert get_year({"release_date_original": "1991"}) == "1991"

    def test_missing_date_returns_placeholder(self):
        assert get_year({}) == "????"

    def test_empty_date_returns_placeholder(self):
        assert get_year({"release_date_original": ""}) == "????"


# ─────────────────────────────────────────────────────────────────────────────
# get_quality_tag
# ─────────────────────────────────────────────────────────────────────────────

class TestGetQualityTag:
    def test_full_tag(self):
        album = {"maximum_bit_depth": 24, "maximum_sampling_rate": 96.0}
        assert get_quality_tag(album) == "FLAC 24bit 96kHz"

    def test_cd_quality(self):
        album = {"maximum_bit_depth": 16, "maximum_sampling_rate": 44.1}
        assert get_quality_tag(album) == "FLAC 16bit 44kHz"

    def test_missing_fields_returns_plain_flac(self):
        assert get_quality_tag({}) == "FLAC"

    def test_zero_bit_depth_returns_plain_flac(self):
        assert get_quality_tag({"maximum_bit_depth": 0, "maximum_sampling_rate": 96}) == "FLAC"


# ─────────────────────────────────────────────────────────────────────────────
# apply_version_to_title
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyVersionToTitle:
    def test_appends_version(self):
        data = {"title": "OK Computer", "version": "Remastered"}
        apply_version_to_title(data)
        assert data["title"] == "OK Computer (Remastered)"

    def test_no_version_field_noop(self):
        data = {"title": "OK Computer"}
        apply_version_to_title(data)
        assert data["title"] == "OK Computer"

    def test_empty_version_noop(self):
        data = {"title": "OK Computer", "version": ""}
        apply_version_to_title(data)
        assert data["title"] == "OK Computer"

    def test_whitespace_only_version_noop(self):
        data = {"title": "OK Computer", "version": "   "}
        apply_version_to_title(data)
        assert data["title"] == "OK Computer"

    def test_not_double_appended(self):
        data = {"title": "OK Computer (Remastered)", "version": "Remastered"}
        apply_version_to_title(data)
        assert data["title"] == "OK Computer (Remastered)"

    def test_version_stripped_of_surrounding_whitespace(self):
        data = {"title": "Dummy", "version": "  Deluxe Edition  "}
        apply_version_to_title(data)
        assert data["title"] == "Dummy (Deluxe Edition)"

# ─────────────────────────────────────────────────────────────────────────────
# strip_feat_from_track_title
# ─────────────────────────────────────────────────────────────────────────────
class TestTrackHasFeaturedArtist:
    def test_returns_true_if_featured_artist_present(self):
        track = {"performers": "Main Artist - FeaturedArtist"}
        assert _track_has_featured_artist(track) is True

    def test_returns_false_if_no_featured_artist(self):
        track = {"performers": "Main Artist - Producer"}
        assert _track_has_featured_artist(track) is False

    def test_returns_false_if_performers_missing_or_empty(self):
        assert _track_has_featured_artist({}) is False
        assert _track_has_featured_artist({"performers": ""}) is False

class TestStripFeatFromTrackTitle:
    # helper: build a track dict with a FeaturedArtist marker
    @staticmethod
    def _track(title, has_featured=True):
        performers = "Some Artist - FeaturedArtist" if has_featured else "Some Artist - MainArtist"
        return {"title": title, "performers": performers}

    def test_strips_feat_parentheses(self):
        t = self._track("Song (feat. Guest)")
        strip_feat_from_track_title(t)
        assert t["title"] == "Song"

    def test_strips_ft_parentheses(self):
        t = self._track("Song (ft. Guest)")
        strip_feat_from_track_title(t)
        assert t["title"] == "Song"

    def test_strips_featuring_brackets(self):
        t = self._track("Song [featuring Guest Artist]")
        strip_feat_from_track_title(t)
        assert t["title"] == "Song"

    def test_strips_feat_curly(self):
        t = self._track("Song {feat. Guest}")
        strip_feat_from_track_title(t)
        assert t["title"] == "Song"

    def test_case_insensitive(self):
        t = self._track("Song (FEAT. Guest)")
        strip_feat_from_track_title(t)
        assert t["title"] == "Song"

    def test_noop_when_no_featured_artist_in_performers(self):
        t = self._track("Song (feat. Guest)", has_featured=False)
        strip_feat_from_track_title(t)
        assert t["title"] == "Song (feat. Guest)"

    def test_noop_when_no_performers_key(self):
        t = {"title": "Song (feat. Guest)"}
        strip_feat_from_track_title(t)
        assert t["title"] == "Song (feat. Guest)"

    def test_title_without_feat_unchanged(self):
        t = self._track("Plain Song Title")
        strip_feat_from_track_title(t)
        assert t["title"] == "Plain Song Title"


# ─────────────────────────────────────────────────────────────────────────────
# strip_feat_from_album_title
# ─────────────────────────────────────────────────────────────────────────────

class TestStripFeatFromAlbumTitle:
    """Album title stripping does not check performers — always strips if pattern matches."""

    def test_strips_feat_parentheses(self):
        album = {"title": "Album (feat. Guest)"}
        strip_feat_from_album_title(album)
        assert album["title"] == "Album"

    def test_strips_featuring_brackets(self):
        album = {"title": "Album [featuring Someone]"}
        strip_feat_from_album_title(album)
        assert album["title"] == "Album"

    def test_no_feat_unchanged(self):
        album = {"title": "A Normal Album Title"}
        strip_feat_from_album_title(album)
        assert album["title"] == "A Normal Album Title"

    def test_empty_title(self):
        album = {"title": ""}
        strip_feat_from_album_title(album)
        assert album["title"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# resolve_url
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveUrl:
    def test_play_album_url(self):
        assert resolve_url("https://play.qobuz.com/album/0060253780948") == ("album", "0060253780948")

    def test_open_album_url(self):
        assert resolve_url("https://open.qobuz.com/album/abc123") == ("album", "abc123")

    def test_play_track_url(self):
        assert resolve_url("https://play.qobuz.com/track/23929921") == ("track", "23929921")

    def test_play_artist_url(self):
        assert resolve_url("https://play.qobuz.com/artist/707261") == ("artist", "707261")

    def test_unrecognised_url_raises(self):
        with pytest.raises(click.ClickException, match="Unrecognised URL"):
            resolve_url("https://www.google.com/")

    def test_bare_id_raises(self):
        with pytest.raises(click.ClickException):
            resolve_url("12345678")


# ─────────────────────────────────────────────────────────────────────────────
# parse_targets
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTargets:
    def test_album_prefix(self):
        assert parse_targets(("al-id", "0060253780948")) == [("album", "0060253780948")]

    def test_track_prefix(self):
        assert parse_targets(("tr-id", "23929921")) == [("track", "23929921")]

    def test_artist_prefix(self):
        assert parse_targets(("ar-id", "707261")) == [("artist", "707261")]

    def test_multiple_ids_under_one_prefix(self):
        result = parse_targets(("ar-id", "111", "222", "333"))
        assert result == [("artist", "111"), ("artist", "222"), ("artist", "333")]

    def test_prefix_switches_type(self):
        result = parse_targets(("al-id", "AAA", "tr-id", "111"))
        assert result == [("album", "AAA"), ("track", "111")]

    def test_url_album(self):
        result = parse_targets(("https://play.qobuz.com/album/xyz",))
        assert result == [("album", "xyz")]

    def test_url_track(self):
        result = parse_targets(("https://play.qobuz.com/track/99",))
        assert result == [("track", "99")]

    def test_url_artist(self):
        result = parse_targets(("https://play.qobuz.com/artist/42",))
        assert result == [("artist", "42")]

    def test_mixed_urls_and_prefixed_ids(self):
        result = parse_targets((
            "https://play.qobuz.com/album/xyz",
            "tr-id", "99",
            "ar-id", "42",
        ))
        assert result == [("album", "xyz"), ("track", "99"), ("artist", "42")]

    def test_url_resets_prefix(self):
        # After a URL, a bare ID should still be rejected
        with pytest.raises(click.ClickException):
            parse_targets((
                "https://play.qobuz.com/album/xyz",
                "12345",                               # bare ID — no active prefix
            ))

    def test_bare_id_no_prefix_raises(self):
        with pytest.raises(click.ClickException, match="Bare ID"):
            parse_targets(("12345678",))

    def test_dangling_prefix_raises(self):
        with pytest.raises(click.ClickException):
            parse_targets(("al-id",))   # no ID follows

    def test_empty_tuple_returns_empty_list(self):
        assert parse_targets(()) == []
