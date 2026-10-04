import unittest
from pathlib import Path

from harness import run_suite

ROOT = Path(__file__).resolve().parent.parent


class RegressionMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_suite(ROOT / "specs" / "wv_nipa2", ROOT / "fixtures" / "cases.json")

    def test_every_case_matches_expected_verdict(self):
        for row in self.report["cases"]:
            with self.subTest(case=row["case"]):
                self.assertEqual(
                    row["outcome"], "as_expected",
                    f"{row['case']}: expected {row['expected_failures']}, caught {row['caught']}")

    def test_good_output_passes_all_checks(self):
        good = next(r for r in self.report["cases"] if r["case"] == "good_corporate")
        self.assertEqual(good["output_verdict"], "pass", good["checks"])
        self.assertEqual(good["caught"], [])


if __name__ == "__main__":
    unittest.main()
