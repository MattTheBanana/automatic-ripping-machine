"""Tests for conservative Blu-ray candidate analysis and incremental-rip inventory."""
import json

from arm.ripper.disc_analysis import (
    DiscRipInventory,
    analyze_title_candidates,
    parse_segment_map,
    rank_main_feature_candidates,
)


class FakeTrack:
    def __init__(self, track_number, filename, length, filesize, chapters, playlist="", segment_map=""):
        self.track_number = str(track_number)
        self.filename = filename
        self.length = length
        self.filesize = filesize
        self.chapters = chapters
        self.playlist = playlist
        self.segment_map = segment_map


def test_segment_map_preserves_play_order():
    assert parse_segment_map("511,507,512,515") == (511, 507, 512, 515)
    assert parse_segment_map("511, invalid, 507") == (511, 507)


def test_candidate_analysis_flags_different_ordered_segment_maps():
    first = FakeTrack(
        42, "Movie-FPL_MainFeature_t42.mkv", 8774, 29_000_000_000, 16,
        "00778.mpls", "511,507,512,515"
    )
    second = FakeTrack(
        164, "Movie-FPL_MainFeature_t164.mkv", 8774, 29_100_000_000, 16,
        "00795.mpls", "511,507,512,516"
    )
    warnings = analyze_title_candidates([first, second])
    assert len(warnings) == 1
    assert warnings[0]["kind"] == "different_segment_maps"
    assert "position 4" in warnings[0]["message"]
    assert warnings[0]["left"]["playlist"] == "00778.mpls"


def test_candidates_without_segment_maps_are_only_metadata_warnings():
    first = FakeTrack(1, "A_MainFeature.mkv", 3600, 10_000, 10)
    second = FakeTrack(2, "B.mkv", 3600, 10_100, 10)
    assert analyze_title_candidates([first, second])[0]["kind"] == "metadata_only"


def test_rank_prefers_main_feature_label_when_runtimes_are_close():
    unlabeled = FakeTrack(42, "Movie_t42.mkv", 8774, 29_000_000_000, 16)
    labeled = FakeTrack(164, "Movie_FPL_MainFeature_t164.mkv", 8770, 28_900_000_000, 16)
    assert rank_main_feature_candidates([unlabeled, labeled])[0] is labeled


def test_incremental_inventory_requires_record_and_existing_nonempty_output(tmp_path):
    log_dir = tmp_path / "logs"
    completed = tmp_path / "completed"
    raw = tmp_path / "raw"
    completed.mkdir()
    raw.mkdir()
    track = FakeTrack(42, "Movie_t42.mkv", 8774, 29_000_000_000, 16, "00795.mpls", "1,2,3")
    source = raw / track.filename
    source.write_bytes(b"mkv data")

    inventory = DiscRipInventory(str(log_dir), str(completed), "DISC", "Movie", "bluray", [track])
    assert inventory.record_success(track, str(source), aliases=["Movie.mkv"])
    assert (log_dir / f"{inventory.fingerprint}.json").exists()
    assert not inventory.has_successful_output(track)

    (completed / "Movie.mkv").write_bytes(b"verified output")
    refreshed = DiscRipInventory(str(log_dir), str(completed), "DISC", "Movie", "bluray", [track])
    assert refreshed.has_successful_output(track)

    (completed / "Movie.mkv").write_bytes(b"")
    refreshed = DiscRipInventory(str(log_dir), str(completed), "DISC", "Movie", "bluray", [track])
    assert not refreshed.has_successful_output(track)

    saved = json.loads((log_dir / f"{inventory.fingerprint}.json").read_text())
    assert saved["tracks"]


def test_inventory_changes_when_segment_order_changes(tmp_path):
    one = FakeTrack(4, "movie.mkv", 1200, 1000, 10, "00001.mpls", "1,2,3")
    two = FakeTrack(4, "movie.mkv", 1200, 1000, 10, "00001.mpls", "3,2,1")
    inventory_a = DiscRipInventory(str(tmp_path / "logs"), str(tmp_path / "completed"),
                                   "DISC", "Movie", "bluray", [one])
    inventory_b = DiscRipInventory(str(tmp_path / "logs"), str(tmp_path / "completed"),
                                   "DISC", "Movie", "bluray", [two])
    assert inventory_a.fingerprint != inventory_b.fingerprint
