import unittest
from types import SimpleNamespace
from unittest.mock import patch

import arm.ripper.utils as ripper_utils
from arm.api.json_api import parse_makemkv_progress
from arm.ripper.arm_ripper import _apply_disc_feature_defaults
from arm.models.job import Job

from arm.ripper.utils import (
    clean_for_filename, fix_job_title, format_failure_notification, DuplicateRunException
)
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


class TestMakeMKVProgressParsing(unittest.TestCase):
    def test_parses_current_title_and_total_progress_separately(self):
        lines = [
            'PRGT:5020,0,"Saving all titles"',
            'PRGC:5018,0,"Saving title 2 of 4"',
            "PRGV:32768,16384,65536",
            "PRGV:39321,19660,65536",
        ]
        result = parse_makemkv_progress(lines)
        self.assertEqual(result["current_title"], "Saving title 2 of 4")
        self.assertEqual(result["total_title"], "Saving all titles")
        self.assertEqual(result["current_title_code"], "5018")
        self.assertAlmostEqual(result["current_title_progress"], 60.0, places=1)
        self.assertAlmostEqual(result["total_progress"], 30.0, places=1)
        self.assertTrue(result["has_progress_values"])

    def test_accepts_small_values_and_escaped_title_text(self):
        result = parse_makemkv_progress([
            'PRGC:5001,0,"Saving \\"Special title\\""',
            "PRGV:1,2,4",
        ])
        self.assertEqual(result["current_title"], 'Saving "Special title"')
        self.assertAlmostEqual(result["current_title_progress"], 25.0)
        self.assertAlmostEqual(result["total_progress"], 50.0)

    def test_missing_or_invalid_progress_values_return_zero_percent(self):
        result = parse_makemkv_progress([
            'PRGT:5020,0,"Saving all titles"',
            "PRGV:0,0,0",
        ])
        self.assertFalse(result["has_progress_values"])
        self.assertEqual(result["current_title_progress"], 0.0)
        self.assertEqual(result["total_progress"], 0.0)


class TestFailureNotificationFormatting(unittest.TestCase):
    def test_setup_failure_includes_drive_diagnosis_and_log_action(self):
        message = format_failure_notification(
            "/dev/sr0",
            "Timed out waiting for drive to be ready (ioctl tray status: CDS.TRAY_OPEN).",
            "arm.log",
            setup=True,
        )
        self.assertIn("/dev/sr0", message)
        self.assertIn("CDS.TRAY_OPEN", message)
        self.assertIn("tray is reported open", message)
        self.assertIn("[View log: arm.log]", message)

    def test_long_failure_messages_keep_log_action_and_fit_notification_column(self):
        message = format_failure_notification(
            "A very long disc label " * 8, "read error " * 100, "disc.log"
        )
        self.assertLessEqual(len(message), 256)
        self.assertTrue(message.endswith("[View log: disc.log]"))

    def test_unsafe_log_paths_fall_back_to_arm_log(self):
        message = format_failure_notification("disc", "failed", "../outside.log")
        self.assertIn("[View log: arm.log]", message)

    def test_cancelled_job_uses_cancelled_language(self):
        message = format_failure_notification(
            "SHARK_BOY_AND_LAVA_GIRL", "The tray was opened.", "shark-boy.log",
            outcome="Job cancelled",
        )
        self.assertIn("Job cancelled for SHARK_BOY_AND_LAVA_GIRL", message)
        self.assertTrue(message.endswith("[View log: shark-boy.log]"))


class TestCancelledJobCleanup(unittest.TestCase):
    def test_cancelled_read_releases_job_without_toggling_tray(self):
        drive = SimpleNamespace(
            release_current_job=unittest.mock.Mock(),
            tray_status=unittest.mock.Mock(),
            eject=unittest.mock.Mock(),
        )
        job = SimpleNamespace(
            ejected=False,
            drive=drive,
            devpath="/dev/sr0",
            _arm_abort_reason="The tray was opened during reading.",
        )
        Job.eject(job)
        drive.release_current_job.assert_called_once_with()
        drive.tray_status.assert_not_called()
        drive.eject.assert_not_called()


class TestDuplicateRunGuard(unittest.TestCase):
    def test_duplicate_active_job_raises_benign_exception(self):
        active_job = SimpleNamespace(
            job_id=42, status="ripping", devpath="/dev/sr0", pid=123, pid_hash=456
        )
        with patch("arm.ripper.utils.db.session.query") as query, \
                patch("arm.ripper.utils._job_process_is_alive", return_value=True):
            query.return_value.filter.return_value.all.return_value = [active_job]
            with self.assertRaises(DuplicateRunException):
                ripper_utils.duplicate_run_check("/dev/sr0")
        self.assertEqual(active_job.status, "ripping")


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

    def test_music_jobs_monitor_active_audio_reads(self):
        watchdog, _job, _snapshot = self.make_watchdog(
            status="ripping", disctype="music", timeout=10
        )
        self.assertFalse(watchdog._poll_once(now=100))
        self.assertTrue(watchdog._poll_once(now=110))
        self.assertTrue(watchdog._is_reading_from_drive())

    def test_data_disc_is_monitored_only_while_copy_job_is_active(self):
        watchdog, job, _snapshot = self.make_watchdog(
            status="active", disctype="data", timeout=10
        )
        self.assertTrue(watchdog._is_reading_from_drive())
        job.ejected = True
        self.assertFalse(watchdog._is_reading_from_drive())

    def test_expected_auto_eject_disables_tray_open_cancellation(self):
        watchdog, job, _snapshot = self.make_watchdog(status="ripping", timeout=10)
        self.assertTrue(watchdog._is_reading_from_drive())
        job.ejected = True
        self.assertFalse(watchdog._is_reading_from_drive())

    def test_open_tray_terminates_active_reader_and_records_cancel_reason(self):
        watchdog, job, _snapshot = self.make_watchdog(status="ripping", timeout=10)
        job.pid = 12345
        job.devpath = "/dev/sr0"
        child_process = SimpleNamespace(terminate=unittest.mock.Mock(), kill=unittest.mock.Mock())
        parent_process = SimpleNamespace(children=unittest.mock.Mock(return_value=[child_process]))
        with patch("arm.ripper.utils.os.getpid", return_value=12345), \
                patch("arm.ripper.utils.psutil.Process", return_value=parent_process), \
                patch("arm.ripper.utils.psutil.wait_procs", return_value=([child_process], [])) as wait_procs, \
                patch("arm.ripper.utils.os.kill") as kill:
            watchdog._abort_for_open_tray()
        self.assertIn("tray was opened", job._arm_abort_reason.lower())
        child_process.terminate.assert_called_once_with()
        wait_procs.assert_called_once()
        kill.assert_not_called()

    def test_open_tray_falls_back_to_signalling_worker_between_commands(self):
        watchdog, job, _snapshot = self.make_watchdog(status="ripping", timeout=10)
        job.pid = 12345
        with patch("arm.ripper.utils.os.getpid", return_value=12345), \
                patch("arm.ripper.utils.psutil.Process") as process, \
                patch("arm.ripper.utils.os.kill") as kill:
            process.return_value.children.return_value = []
            watchdog._abort_for_open_tray()
        kill.assert_called_once_with(12345, ripper_utils.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
