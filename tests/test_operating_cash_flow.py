"""Check signed quarters, the Q4 subtraction and original-filing selection."""

import unittest
from datetime import date
from types import SimpleNamespace

from load_operating_cash_flow import TAGS, quarterly_operating_cash_flow, ytd_fact


class OperatingCashFlowTest(unittest.TestCase):
    def setUp(self):
        self.periods, self.records, self.dates = [], [], {}
        # Year-to-date millions: Q2 is a cash outflow quarter (9 - 10 = -1).
        for q, end, ytd in [(1, "03-31", 10), (2, "06-30", 9), (3, "09-30", 15), (4, "12-31", 30)]:
            start = date(2025, 3 * q - 2, 1)
            end = date.fromisoformat("2025-" + end)
            self.periods.append(SimpleNamespace(fiscal_quarter=q, period_start=start, period_end=end))
            accn = f"filing-{q}"
            self.dates[accn] = end.isoformat()
            self.records.append(dict(start="2025-01-01", end=end.isoformat(), val=ytd * 1_000_000,
                                     accn=accn, form="10-K" if q == 4 else "10-Q", filed=end.isoformat()))

    def extract(self):
        return quarterly_operating_cash_flow("TEST", 2025, self.periods, {TAGS[0]: self.records},
                                             {}, self.dates)

    def test_negative_quarter_and_q4_from_annual(self):
        rows = self.extract()
        self.assertEqual([r["operating_cash_flow_usd"] for r in rows],
                         [10_000_000, -1_000_000, 6_000_000, 15_000_000])
        self.assertEqual(sum(r["operating_cash_flow_usd"] for r in rows), 30_000_000)
        self.assertEqual(rows[3]["source_facts"]["current_ytd"]["form"], "10-K")
        self.assertEqual(rows[3]["source_facts"]["previous_ytd"]["accn"], "filing-3")

    def test_missing_cumulative_input_stops(self):
        del self.records[2]
        with self.assertRaisesRegex(ValueError, "missing cumulative"):
            self.extract()

    def test_later_comparative_is_not_an_original_filing(self):
        start, end = "2025-01-01", "2025-03-31"
        comparative = dict(self.records[0], val=11_000_000, accn="next-year", filed="2026-04-30")
        dates = dict(self.dates, **{"next-year": "2026-03-31"})
        fact = ytd_fact("TEST", 2025, 1, start, end, {TAGS[0]: [self.records[0], comparative]}, dates)
        self.assertEqual(fact["accn"], "filing-1")

    def test_same_day_conflict_stops(self):
        self.records.append(dict(self.records[0], val=12_000_000, accn="filing-1b"))
        self.dates["filing-1b"] = "2025-03-31"
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.extract()


if __name__ == "__main__":
    unittest.main()
