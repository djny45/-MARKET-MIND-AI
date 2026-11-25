"""External evidence intake must stay fail-closed and never self-certify."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import external_evidence  # noqa: E402


def _completed_bundle(directory: Path, check_id: str = "EXT-01") -> Path:
    """Build a synthetic *structurally complete* bundle for validator tests only.

    These fixtures test the intake contract; they are never recorded as external
    validation evidence for EXT-01/02/03.
    """
    spec = external_evidence.SPECS[check_id]
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name in spec["artifacts"]:
        artifact = directory / name
        artifact.write_text(f"fixture content for {name}\n", encoding="utf-8")
        artifacts[name] = {
            "path": name,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        }
    bundle = external_evidence.build_template(check_id)
    bundle.update({
        "bundle_id": "validator-fixture-001",
        "outcome": "passed",
        "environment": "authorized-cloud-account",
        "operator_identity": "Test Fixture (not external evidence)",
        "owner_identity": "Test Fixture (not external evidence)",
        "executed_at": "2026-11-24T00:00:00Z",
        "artifacts": artifacts,
        "checks": {name: True for name in spec["checks"]},
    })
    path = directory / "bundle.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path


class ExternalEvidenceTests(unittest.TestCase):
    def test_template_is_pending_and_incomplete(self):
        template = external_evidence.build_template("EXT-03")
        self.assertEqual(template["outcome"], "pending")
        self.assertEqual(template["acceptance_id"], "ACC-031")
        self.assertEqual(template["external_approval"], "not_claimed")
        self.assertTrue(all(value is False for value in template["checks"].values()))
        self.assertTrue(all(not item["sha256"] for item in template["artifacts"].values()))

    def test_template_does_not_close_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(external_evidence.build_template("EXT-02")), encoding="utf-8")
            result = external_evidence.validate_bundle(path)
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["closure_allowed"])
        self.assertIn("outcome is 'pending', not 'passed'", result["findings"])

    def test_complete_structure_is_accepted_but_not_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = external_evidence.validate_bundle(_completed_bundle(Path(tmp)))
        self.assertEqual(result["status"], "valid")
        self.assertTrue(result["closure_allowed"])
        self.assertEqual(result["external_approval"], "not_claimed")

    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = _completed_bundle(directory)
            (directory / "restore-report.json").write_text("tampered\n", encoding="utf-8")
            result = external_evidence.validate_bundle(path)
        self.assertFalse(result["closure_allowed"])
        self.assertIn("artifact hash mismatch: restore-report.json", result["findings"])

    def test_mock_environment_cannot_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = _completed_bundle(directory)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["environment"] = "local moto fake S3"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = external_evidence.validate_bundle(path)
        self.assertFalse(result["closure_allowed"])
        self.assertTrue(any("non-production environment marker" in item
                            for item in result["findings"]))

    def test_secret_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _completed_bundle(Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["notes"] = "AKIA1234567890ABCDEF"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = external_evidence.validate_bundle(path)
        self.assertFalse(result["closure_allowed"])
        self.assertIn("secret-looking value: aws_access_key_id", result["findings"])

    def test_self_certification_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _completed_bundle(Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["external_approval"] = "approved"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = external_evidence.validate_bundle(path)
        self.assertFalse(result["closure_allowed"])

    def test_audit_reports_counts_without_mutating_inventory(self):
        inventory = ROOT / "docs" / "acceptance-inventory.json"
        before = inventory.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            report = external_evidence.audit_inventory(inventory, Path(tmp))
        self.assertEqual(inventory.read_bytes(), before)
        self.assertEqual(report["total_items"], 40)
        self.assertEqual(report["verified"], 37)
        self.assertEqual(report["blocked"], 3)
        self.assertEqual(report["completion_percentage"], 92.5)
        self.assertFalse(report["statuses_mutated"])
        self.assertTrue(all(not item["closure_allowed"] for item in report["intake"]))


if __name__ == "__main__":
    unittest.main()
