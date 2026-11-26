import unittest

from app.skill_catalog import list_skills
from app.skill_integrity import (
    audit_catalog,
    audit_reference_skills,
    audit_workers,
    frontmatter,
    full_integrity_report,
)


class SkillIntegrityTests(unittest.TestCase):
    def test_frontmatter_parsing(self):
        meta = frontmatter("---\nname: demo\ndescription: A demo skill\n---\n# Body\n")
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(meta["description"], "A demo skill")
        self.assertEqual(frontmatter("# no frontmatter"), {})

    def test_catalog_skills_are_valid(self):
        report = audit_catalog()
        self.assertEqual(report["count"], 326)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["activation"], "allowlisted_and_loadable")

    def test_reference_skills_are_present_but_not_registered(self):
        report = audit_reference_skills()
        self.assertEqual(report["count"], 89)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["activation"], "reference_only_not_registered")
        catalog_ids = {skill["id"] for skill in list_skills()}
        self.assertFalse(catalog_ids.intersection(entry["id"] for entry in report["entries"]))

    def test_workers_have_valid_metadata_and_resolvable_skills(self):
        report = audit_workers()
        self.assertEqual(report["count"], 550)
        self.assertEqual(report["departments"], 20)
        self.assertEqual(report["issues"], [])

    def test_full_report_counts_match_verified_inventory(self):
        report = full_integrity_report()
        self.assertEqual(report["catalog_skills"], 326)
        self.assertEqual(report["reference_skills"], 89)
        self.assertEqual(report["total_skill_definitions"], 415)
        self.assertEqual(report["workers"], 550)
        self.assertEqual(report["total_issues"], 0)
        self.assertFalse(report["brokerage_execution"])


if __name__ == "__main__":
    unittest.main()
