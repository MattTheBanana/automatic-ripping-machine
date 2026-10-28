"""Regression checks for the double-feature selection and active-rip layout."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class TestDoubleFeatureLayout(unittest.TestCase):
    def test_double_feature_jobs_use_a_full_width_dashboard_column(self):
        common_js = (ROOT / "arm/ui/static/js/common.js").read_text(encoding="utf-8")
        styles = (ROOT / "arm/ui/static/css/arm-modern.css").read_text(encoding="utf-8")

        self.assertIn(
            '? "col-12 arm-job-column arm-job-column-double-feature"',
            common_js,
        )
        self.assertIn(
            ".arm-job-column-double-feature {\n  flex: 0 0 100%;\n  max-width: 100%;",
            styles,
        )

    def test_feature_summaries_and_rip_settings_have_two_desktop_columns(self):
        styles = (ROOT / "arm/ui/static/css/arm-modern.css").read_text(encoding="utf-8")

        self.assertIn(
            ".arm-job-double-feature-media {\n  display: grid;\n"
            "  grid-template-columns: repeat(2, minmax(0, 1fr));",
            styles,
        )
        self.assertIn(
            ".arm-job-double-feature-details {\n  display: grid;\n"
            "  grid-template-columns: repeat(2, minmax(0, 1fr));",
            styles,
        )
        self.assertIn(
            ".arm-job-double-feature-details { grid-template-columns: minmax(0, 1fr);",
            styles,
        )

    def test_title_search_explains_feature_a_and_b_selection(self):
        title_search = (
            ROOT / "arm/ui/jobs/templates/titlesearch.html"
        ).read_text(encoding="utf-8")
        results = (
            ROOT / "arm/ui/jobs/templates/list_titles.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Enable double-feature mode — select two titles", title_search)
        self.assertIn("Choose as Feature A", results)
        self.assertIn("Choose as Feature B", results)
        self.assertIn("Save both titles", results)


if __name__ == "__main__":
    unittest.main()
