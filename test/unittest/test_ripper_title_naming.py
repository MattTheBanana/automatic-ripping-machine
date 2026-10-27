import unittest
from types import SimpleNamespace
from unittest.mock import patch

import arm.ripper.utils as ripper_utils
from arm.ripper.arm_ripper import _apply_disc_feature_defaults

from arm.ripper.utils import clean_for_filename, fix_job_title
from arm.ui.utils import clean_for_filename as ui_clean_for_filename
from arm.media_metadata import parse_media_label, select_best_media_result, title_search_variants


class TestMediaFolderNaming(unittest.TestCase):
    def make_job(self, title, year="2022", folder_id_type="none", tmdb_id=None, imdb_id=None):
        return SimpleNamespace(
            title=title,
            title_manual=None,
            label="DISC_LABEL",
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            config=SimpleNamespace(FOLDER_ID_TYPE=folder_id_type),
            video_type="movie",
            season_number=None,
            disc_number=None,
            episode_start=None,
            episode_end=None,
        )

    def test_filename_cleaner_preserves_spaces_and_real_hyphens(self):
        self.assertEqual(clean_for_filename("The_Dark_Knight"), "The Dark Knight")
        self.assertEqual(clean_for_filename("Spider-Man: No Way Home"), "Spider-Man - No Way Home")
        self.assertEqual(ui_clean_for_filename("Spider-Man: No Way Home"), "Spider-Man - No Way Home")
        self.assertEqual(ui_clean_for_filename("The_Dark_Knight"), clean_for_filename("The_Dark_Knight"))

    def test_default_folder_name_does_not_add_provider_id(self):
        job = self.make_job("The_Dark_Knight", year="2008", folder_id_type="none", tmdb_id="155")
        self.assertEqual(fix_job_title(job), "The Dark Knight (2008)")

    def test_tmdb_folder_name_uses_jellyfin_identifier_format(self):
        job = self.make_job("The_Dark_Knight", year="2008", folder_id_type="tmdb", tmdb_id="155")
        self.assertEqual(fix_job_title(job), "The Dark Knight (2008) [tmdbid-155]")

    def test_imdb_folder_name_uses_jellyfin_identifier_format(self):
        job = self.make_job("Spider-Man", year="2002", folder_id_type="imdb", imdb_id="tt0145487")
        self.assertEqual(fix_job_title(job), "Spider-Man (2002) [imdbid-tt0145487]")

    def test_missing_provider_id_keeps_normal_folder_name(self):
        job = self.make_job("Spider-Man", year="2002", folder_id_type="tmdb", tmdb_id=None)
        self.assertEqual(fix_job_title(job), "Spider-Man (2002)")

    def test_title_variants_split_joined_words(self):
        self.assertIn("sherlock holmes", [v.lower() for v in title_search_variants("sherlockholmes")])
        self.assertIn("my hero academia", [v.lower() for v in title_search_variants("Myheroacademia")])

    def test_automatic_matching_prefers_exact_show_title_over_fuzzy_movie(self):
        results = [
            {"Title": "My Hero Academia: Two Heroes", "Year": "2018", "Type": "movie"},
            {"Title": "My Hero Academia", "Year": "2016", "Type": "series"},
        ]
        selected = select_best_media_result(results, title="My Hero Academia", prefer_series=False)
        self.assertEqual(selected["Type"], "series")

    def test_disc_label_parser_extracts_given_details_without_guessing(self):
        jump = parse_media_label("21_JUMP_STREET_2012")
        self.assertEqual(jump["title"], "21 Jump Street")
        self.assertEqual(jump["year"], "2012")
        self.assertIsNone(jump["season_number"])
        self.assertIsNone(jump["disc_number"])
        self.assertIsNone(jump["episode_start"])
        self.assertIsNone(jump["episode_end"])

        anime = parse_media_label("Myheroacademia_d1")
        self.assertEqual(anime["title"], "My Hero Academia")
        self.assertEqual(anime["disc_number"], 1)
        self.assertIsNone(anime["year"])
        self.assertIsNone(anime["season_number"])
        self.assertIsNone(anime["episode_start"])
        self.assertIsNone(anime["episode_end"])

    def test_explicit_season_episode_range_and_disc_are_detected(self):
        label = parse_media_label("SHERLOCK_S01E01-E03_DISC02")
        self.assertEqual(label["title"], "Sherlock")
        self.assertEqual(label["season_number"], 1)
        self.assertEqual(label["disc_number"], 2)
        self.assertEqual(label["episode_start"], 1)
        self.assertEqual(label["episode_end"], 3)

        episode_only = parse_media_label("SHERLOCK_E01-E03")
        self.assertEqual(episode_only["title"], "Sherlock")
        self.assertIsNone(episode_only["season_number"])
        self.assertEqual(episode_only["episode_start"], 1)
        self.assertEqual(episode_only["episode_end"], 3)

    def test_movie_disc_two_automatically_selects_special_features(self):
        job = self.make_job("Jaws", year="1975")
        job.video_type = "movie"
        job.disc_number = 2
        job.special_features = False
        job.special_features_auto = True
        with patch("arm.ripper.arm_ripper.db.session.commit"):
            _apply_disc_feature_defaults(job)
        self.assertTrue(job.special_features)

    def test_auto_special_features_does_not_select_series_disc_two(self):
        job = self.make_job("Sherlock", year="2010")
        job.video_type = "series"
        job.disc_number = 2
        job.special_features = False
        job.special_features_auto = True
        with patch("arm.ripper.arm_ripper.db.session.commit"):
            _apply_disc_feature_defaults(job)
        self.assertFalse(job.special_features)

    def test_manual_special_feature_choice_is_preserved(self):
        job = self.make_job("Jaws", year="1975")
        job.video_type = "movie"
        job.disc_number = 1
        job.special_features = True
        job.special_features_auto = False
        with patch("arm.ripper.arm_ripper.db.session.commit"):
            _apply_disc_feature_defaults(job)
        self.assertTrue(job.special_features)

    def test_movie_disc_two_uses_the_same_movie_folder_name(self):
        disc_one = self.make_job("Jaws", year="1975")
        disc_two = self.make_job("Jaws", year="1975")
        disc_one.disc_number = 1
        disc_two.disc_number = 2
        self.assertEqual(fix_job_title(disc_one), fix_job_title(disc_two))

    def test_special_feature_movie_files_go_to_extras_subfolder(self):
        job = self.make_job("Jaws", year="1975")
        job.path = "/media/completed/movie/Jaws (1975)"
        job.special_features = True
        job.hasnicetitle = True
        job.config.EXTRAS_SUB = "extras"
        job.config.DEST_EXT = "mkv"
        with patch("arm.ripper.utils.make_dir"), patch("arm.ripper.utils.move_files_main") as mover:
            ripper_utils.move_files("/tmp/transcode", "feature-01.mkv", job, False)
        self.assertEqual(
            mover.call_args.args[1],
            "/media/completed/movie/Jaws (1975)/extras/feature-01.mkv",
        )

    def test_special_feature_movie_without_extras_subfolder_stays_in_movie_folder(self):
        job = self.make_job("Jaws", year="1975")
        job.path = "/media/completed/movie/Jaws (1975)"
        job.special_features = True
        job.hasnicetitle = True
        job.config.EXTRAS_SUB = "none"
        job.config.DEST_EXT = "mkv"
        with patch("arm.ripper.utils.make_dir"), patch("arm.ripper.utils.move_files_main") as mover:
            ripper_utils.move_files("/tmp/transcode", "feature-01.mkv", job, False)
        self.assertEqual(
            mover.call_args.args[1],
            "/media/completed/movie/Jaws (1975)/feature-01.mkv",
        )

    def test_series_output_includes_episode_range_and_one_provider_id(self):
        job = self.make_job("Sherlock [imdbid-tt1475582]", year="2010",
                            folder_id_type="imdb", imdb_id="tt1475582")
        job.video_type = "series"
        job.season_number, job.disc_number = 1, 2
        job.episode_start, job.episode_end = 1, 3
        self.assertEqual(fix_job_title(job),
                         "Sherlock (2010) - S01E01-E03 [imdbid-tt1475582]")

    def test_unidentified_disc_does_not_become_literal_placeholder_folder(self):
        job = self.make_job("not identified", year="0000", folder_id_type="none")
        job.label = "not identified"
        self.assertEqual(fix_job_title(job), "Unknown Title")



class TestDriveSleepWatchdog(unittest.TestCase):
    def make_watchdog(self, status="ripping", disctype="dvd",
                      direct_drive_source=False, timeout=10):
        job = SimpleNamespace(
            job_id=123,
            devpath="/dev/sr0",
            logfile="test-disc.log",
            status=status,
            disctype=disctype,
            label="Test Disc",
            title="Test Disc",
            stage="Ripping",
        )
        watchdog = ripper_utils.DriveSleepWatchdog(
            job,
            direct_drive_source=direct_drive_source,
            check_interval_seconds=1,
            stall_timeout_seconds=timeout,
        )
        snapshot = {"value": (("test-disc.log", 1, 100),)}

        def snapshot_probe():
            return snapshot["value"]

        watchdog._activity_snapshot = snapshot_probe
        return watchdog, job, snapshot

    def test_alerts_after_stall_and_rearms_when_progress_resumes(self):
        watchdog, _job, snapshot = self.make_watchdog(timeout=10)
        self.assertFalse(watchdog._poll_once(now=100))
        self.assertFalse(watchdog._poll_once(now=109))
        self.assertTrue(watchdog._poll_once(now=110))
        self.assertFalse(watchdog._poll_once(now=130))

        snapshot["value"] = (("test-disc.log", 2, 200),)
        self.assertFalse(watchdog._poll_once(now=131))
        self.assertFalse(watchdog._poll_once(now=140))
        self.assertTrue(watchdog._poll_once(now=141))

    def test_waiting_job_does_not_trigger_stall_alert(self):
        watchdog, job, _snapshot = self.make_watchdog(status="waiting", timeout=10)
        self.assertFalse(watchdog._poll_once(now=100))
        self.assertFalse(watchdog._poll_once(now=1000))

        job.status = "ripping"
        self.assertFalse(watchdog._poll_once(now=1001))
        self.assertTrue(watchdog._poll_once(now=1011))

    def test_transcode_is_monitored_only_when_reading_directly_from_disc(self):
        watchdog, _job, _snapshot = self.make_watchdog(
            status="transcoding", direct_drive_source=False, timeout=10
        )
        self.assertFalse(watchdog._poll_once(now=100))
        self.assertFalse(watchdog._poll_once(now=1000))

        direct_watchdog, _job, _snapshot = self.make_watchdog(
            status="transcoding", direct_drive_source=True, timeout=10
        )
        self.assertFalse(direct_watchdog._poll_once(now=100))
        self.assertTrue(direct_watchdog._poll_once(now=110))

    def test_music_jobs_are_not_monitored_as_optical_video_reads(self):
        watchdog, _job, _snapshot = self.make_watchdog(
            status="ripping", disctype="music", timeout=10
        )
        self.assertFalse(watchdog._poll_once(now=100))
        self.assertFalse(watchdog._poll_once(now=1000))


if __name__ == "__main__":
    unittest.main()
