"""Regression tests for generic optical-disc labels."""
import unittest

from arm.media_metadata import is_generic_disc_title, parse_media_label, title_search_variants


class TestGenericDiscLabels(unittest.TestCase):
    def test_common_placeholder_labels_are_not_search_terms(self):
        for label in (
            "undefined", "video", "DVD", "disc", "disc 1", "Video 2", "CD 1",
            "DVD_VIDEO", "VIDEO_TS", "not identified", "new volume", "unknown_title",
            "Untitled Disc", "undefined_1", "unknown_volume_1",
        ):
            with self.subTest(label=label):
                self.assertTrue(is_generic_disc_title(label), label)
                self.assertEqual(title_search_variants(label), [])

    def test_generic_disc_label_does_not_parse_as_a_media_title(self):
        for label in ("undefined", "video", "DVD_VIDEO", "disc 1"):
            with self.subTest(label=label):
                self.assertEqual(parse_media_label(label)["title"], "")

    def test_real_titles_remain_searchable(self):
        for title in ("Jaws", "The Matrix", "Shark Boy and Lava Girl"):
            with self.subTest(title=title):
                self.assertFalse(is_generic_disc_title(title))
                self.assertTrue(title_search_variants(title))


if __name__ == "__main__":
    unittest.main()
