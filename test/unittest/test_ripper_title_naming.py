import unittest
from types import SimpleNamespace

from arm.ripper.utils import clean_for_filename, fix_job_title
from arm.ui.utils import clean_for_filename as ui_clean_for_filename
from arm.media_metadata import parse_media_label, title_search_variants


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


if __name__ == "__main__":
    unittest.main()
