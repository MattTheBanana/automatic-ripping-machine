import unittest
from types import SimpleNamespace

from arm.ripper.utils import clean_for_filename, fix_job_title
from arm.ui.utils import clean_for_filename as ui_clean_for_filename


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


if __name__ == "__main__":
    unittest.main()
