"""Local ingress-gate validator must fail closed on all public gates."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ingress_gate_check.py"


class IngressGateCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=str(ROOT),
            capture_output=True, text=True, timeout=180,
        )
        cls.returncode = result.returncode
        cls.stdout = result.stdout
        cls.stderr = result.stderr
        cls.report = json.loads(result.stdout) if result.stdout.strip() else {}

    def test_script_runs_and_fails_closed(self):
        self.assertEqual(self.returncode, 0, self.stderr)
        self.assertFalse(self.report["public_ingress_enabled"])
        self.assertEqual(self.report["total"], 6)
        self.assertEqual(self.report["passed"], 0)
        self.assertEqual({g["id"] for g in self.report["gates"]},
                         {"G1", "G2", "G3", "G4", "G5", "G6"})
        self.assertTrue(all(g["public_status"] == "BLOCKED"
                            for g in self.report["gates"]))

    def test_local_prerequisites_are_reported(self):
        gates = {g["id"]: g for g in self.report["gates"]}
        self.assertEqual(gates["G1"]["local_validation"]["preflight_tls_template"], "pass")
        self.assertEqual(gates["G2"]["local_validation"]["backend_not_host_published"], "pass")
        self.assertTrue(gates["G3"]["local_validation"]["limit_conn"])
        self.assertEqual(gates["G4"]["local_validation"]["EXT_03_outcome"], "pending")
        self.assertFalse(gates["G5"]["local_validation"]["attested_sources_configured"])
        self.assertEqual(gates["G6"]["local_validation"]["EXT_02_outcome"], "pending")

    def test_output_contains_no_secret_values(self):
        for marker in ("DUMMYSECRETKEY", "scrypt$", "MARKET_MIND_CLOUD_SECRET_KEY="):
            self.assertNotIn(marker, self.stdout + self.stderr)


if __name__ == "__main__":
    unittest.main()
