"""Check the split basis, the split guard and the debt rules."""

import unittest
from datetime import date
from decimal import Decimal

from load_valuation_inputs import balance_sheet, check_split_basis, split_factor


SPLITS = [(date(2024, 6, 10), 10)]


class SplitTest(unittest.TestCase):
    def test_factor_counts_only_later_splits(self):
        self.assertEqual(split_factor(SPLITS, "2024-05-29"), 10)
        self.assertEqual(split_factor(SPLITS, "2024-08-28"), 1)

    def test_guard_trips_when_a_split_is_missing(self):
        original = dict(start="2023-01-30", end="2023-04-30", val=Decimal("0.82"), filed="2023-05-26")
        restated = dict(original, val=Decimal("0.082"), filed="2024-08-28")
        self.assertEqual(check_split_basis("TEST", SPLITS, [original, restated]), 1)
        with self.assertRaisesRegex(ValueError, "split ratio"):
            check_split_basis("TEST", [], [original, restated])


class DebtTest(unittest.TestCase):
    dates = {"q": "2025-03-31"}

    def fact(self, val):
        return [dict(end="2025-03-31", val=val, accn="q", form="10-Q", filed="2025-04-30")]

    def test_total_debt_prefers_long_term_debt_and_adds_commercial_paper(self):
        usd = {"LongTermDebt": self.fact(100), "LongTermDebtNoncurrent": self.fact(90),
               "CommercialPaper": self.fact(5), "CashAndCashEquivalentsAtCarryingValue": self.fact(40)}
        debt, method, cash, _ = balance_sheet(usd, "2025-03-31", self.dates)
        self.assertEqual((debt, method, cash), (105, "LongTermDebt", 40))

    def test_no_debt_line_is_labelled(self):
        usd = {"CashAndCashEquivalentsAtCarryingValue": self.fact(40)}
        debt, method, _, _ = balance_sheet(usd, "2025-03-31", self.dates)
        self.assertEqual((debt, method), (0, "no_debt_line_in_filing"))

    def test_missing_cash_stops(self):
        with self.assertRaisesRegex(ValueError, "Missing cash"):
            balance_sheet({}, "2025-03-31", self.dates)


if __name__ == "__main__":
    unittest.main()
