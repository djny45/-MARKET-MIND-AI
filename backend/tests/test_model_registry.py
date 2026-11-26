"""Model metadata must not claim source that is not in the repository."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.model_registry import list_model_integrations  # noqa: E402


class ModelRegistryTests(unittest.TestCase):
    def test_kronos_is_reported_as_not_vendored(self):
        report = list_model_integrations()
        self.assertEqual(report["mode"], "research_metadata_only")
        self.assertEqual(len(report["models"]), 1)
        kronos = report["models"][0]
        self.assertEqual(kronos["id"], "kronos")
        self.assertFalse(kronos["source_imported"])
        self.assertFalse(kronos["pretrained_weights_present"])
        self.assertFalse(kronos["runtime_installed"])
        self.assertFalse(kronos["inference_enabled"])
        self.assertFalse(kronos["execution_enabled"])
        self.assertEqual(kronos["status"], "not_vendored")
        self.assertFalse((REPO_ROOT / "third_party" / "Kronos").exists())
        self.assertFalse(any("Upstream source is vendored under" in note for note in kronos["notes"]))


if __name__ == "__main__":
    unittest.main()
