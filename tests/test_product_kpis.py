"""Check table rows across and down, negative cells, and the revenue guard."""

import unittest
from datetime import date
from types import SimpleNamespace

from load_product_kpis import alphabet, quarter_rows, row_after


class RowTest(unittest.TestCase):
    def test_row_on_one_line(self):
        numbers, source, _ = row_after(["Google Cloud | 11,955 | | | 17,664"], "Google Cloud")
        self.assertEqual(numbers[:2], [11955, 17664])
        self.assertEqual(source, "Google Cloud | 11,955 | | | 17,664")

    def test_row_spread_over_following_lines(self):
        lines = ["AWS", "Net sales", "$", "6,105", "$", "8,381", "Operating expenses"]
        numbers, _, _ = row_after(lines, "Net sales")
        self.assertEqual(numbers[:2], [6105, 8381])

    def test_parenthesised_value_is_negative(self):
        numbers, _, _ = row_after(["Google Cloud | (1,243) | | | (1,013)"], "Google Cloud")
        self.assertEqual(numbers[:2], [-1243, -1013])

    def test_second_row_equal_to_revenue_is_not_operating_income(self):
        lines = ["Google Cloud", "1,709", "2,614", "Total", "Google Cloud", "1,709", "2,614", "Other"]
        found = alphabet(lines, "\n".join(lines))
        self.assertEqual(found["google_cloud_revenue_usd"][0], 2_614_000_000)
        self.assertNotIn("google_cloud_operating_income_usd", found)


class GuardTest(unittest.TestCase):
    def test_segment_above_company_revenue_stops(self):
        body = "Google Cloud | 1,000 | | | 9,000"
        quarter = SimpleNamespace(period_start=date(2025, 1, 1), period_end=date(2025, 3, 31), revenue_usd=5_000_000_000)
        release = {"text": body, "source_url": "u", "_id": "a"}
        with self.assertRaisesRegex(ValueError, "outside 0 to total revenue"):
            quarter_rows("GOOGL", quarter, release)

    def test_missing_kpi_gets_a_note(self):
        quarter = SimpleNamespace(period_start=date(2025, 1, 1), period_end=date(2025, 3, 31), revenue_usd=1)
        rows = quarter_rows("NVDA", quarter, {"text": "no figures here", "source_url": "u", "_id": "a"})
        self.assertIsNone(rows[0]["value"])
        self.assertIn("Not stated", rows[0]["definition_note"])


if __name__ == "__main__":
    unittest.main()
