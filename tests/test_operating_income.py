"""Check source precedence, operating losses and cumulative reconciliation."""

import unittest
from datetime import date
from types import SimpleNamespace

from load_operating_income import TAG, quarterly_operating_income


class OperatingIncomeTest(unittest.TestCase):
    def setUp(self):
        self.periods = []
        self.records = []
        self.dates = {}
        self.refs = {}
        # Rounded USD millions. The annual filing gives a total, not a Q4 fact.
        for q, end, income in [(1, "03-31", -1), (2, "06-30", 2),
                               (3, "09-30", 3), (4, "12-31", 5)]:
            start = date(2025, 3 * q - 2, 1)
            end = date.fromisoformat("2025-" + end)
            self.periods.append(SimpleNamespace(fiscal_quarter=q, period_start=start, period_end=end))
            accn = f"filing-{q}"
            self.dates[accn] = end.isoformat()
            self.records.append(dict(start="2025-01-01", end=end.isoformat(), val=income * 1_000_000,
                                     accn=accn, form="10-K" if q == 4 else "10-Q", filed=end.isoformat()))

    def extract(self):
        return quarterly_operating_income("TEST", 2025, self.periods, {TAG: self.records},
                                          self.refs, self.dates)

    def test_negative_income_and_quarter_difference(self):
        self.assertEqual([r["operating_income_usd"] for r in self.extract()],
                         [-1_000_000, 3_000_000, 1_000_000, 2_000_000])

    def test_reported_q4_keeps_signed_difference(self):
        key = ("TEST", "2025-10-01", "2025-12-31")
        self.refs[key] = {"val": 3_000_000}
        q4 = self.extract()[-1]
        self.assertEqual(q4["operating_income_usd"], 3_000_000)
        self.assertEqual(q4["source_facts"]["four_quarters_minus_annual_usd"], 1_000_000)
        self.refs[key]["val"] = 5_000_000
        with self.assertRaisesRegex(ValueError, "needs reconciliation"):
            self.extract()
