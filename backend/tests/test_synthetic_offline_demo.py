"""Tests for the synthetic offline demo's optional dependency handling."""
import unittest
from unittest.mock import patch


class SyntheticOfflineDemoTests(unittest.TestCase):
    @patch("app.offline_research_pipeline.run_offline_research", side_effect=RuntimeError("Install pandas and numpy to use offline CSV research."))
    def test_missing_optional_dependencies_print_helpful_message(self, run_research):
        from examples.run_synthetic_offline_demo import main
        with patch("sys.stderr") as stderr:
            self.assertEqual(main(), 2)
            stderr.write.assert_called_once_with(
                "Offline demo unavailable: Install pandas and numpy to use offline CSV research.\\n"
            )
        run_research.assert_called_once()


if __name__ == "__main__":
    unittest.main()
