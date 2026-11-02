import os
import unittest
from unittest.mock import patch

from app.main import intelligence_core


class IntelligenceCoreApiTests(unittest.TestCase):
    def test_status_endpoint_reports_disabled_shared_core_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = intelligence_core()
        self.assertEqual(result["core_id"], "shared_central_intelligence")
        self.assertFalse(result["enabled"])
        self.assertEqual(result["provider"], "none")


if __name__ == "__main__":
    unittest.main()
