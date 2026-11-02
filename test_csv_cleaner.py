#!/usr/bin/env python3
"""Self-test for csv_cleaner.py — run: python3 test_csv_cleaner.py"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from csv_cleaner import normalize_date  # noqa: E402

HERE = Path(__file__).parent


class TestNormalizeDate(unittest.TestCase):
    def test_known_formats(self):
        cases = {
            "2026-01-05": "2026-01-05",
            "05/01/2026": "2026-01-05",
            "05-01-2026": "2026-01-05",
            "05.01.2026": "2026-01-05",
            "2026/01/05": "2026-01-05",
            "5 Jan 2026": "2026-01-05",
            "5 January 2026": "2026-01-05",
            "Jan 5, 2026": "2026-01-05",
        }
        for raw, want in cases.items():
            got, _ = normalize_date(raw)
            self.assertEqual(got, want, raw)

    def test_unparseable_passes_through(self):
        got, changed = normalize_date("not a date")
        self.assertEqual(got, "not a date")
        self.assertFalse(changed)


class TestEndToEnd(unittest.TestCase):
    def test_messy_file(self):
        messy = (
            "id,name,order_date\n"
            "1, Asha ,05/01/2026\n"
            ",,\n"
            "id,name,order_date\n"
            "2,Bina,2026-01-06\n"
            "1,Asha,2026-01-05\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.csv"
            dst = Path(tmp) / "out.csv"
            src.write_text(messy, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HERE / "csv_cleaner.py"), str(src),
                 "-o", str(dst), "--dedupe"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(dst, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            # header + 2 unique cleaned rows; the third data row duplicates
            # the first once its date is normalized
            self.assertEqual(rows, [["id", "name", "order_date"],
                                    ["1", "Asha", "2026-01-05"],
                                    ["2", "Bina", "2026-01-06"]])
            self.assertIn("Duplicates removed:  1", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
