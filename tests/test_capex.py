"""Regression checks for selecting an original SEC disclosure."""

import unittest

from load_capex import TAGS, ytd_fact


class CapexFilingTest(unittest.TestCase):
    def test_comparative_with_same_value_cannot_replace_original_filing(self):
        start, end = "2019-01-28", "2019-04-28"
        original = dict(start=start, end=end, val=128_000_000, form="10-Q",
                        filed="2019-05-16", accn="0001045810-19-000079")
        comparative = dict(original, filed="2020-05-21", accn="0001045810-20-000065")
        dates = {original["accn"]: end, comparative["accn"]: "2020-04-26"}
        fact = ytd_fact("NVDA", 2020, 1, start, end, {TAGS[0]: [original, comparative]}, {}, dates)
        self.assertEqual(fact["accn"], original["accn"])
        with self.assertRaisesRegex(ValueError, "missing cumulative"):
            ytd_fact("NVDA", 2020, 1, start, end, {TAGS[0]: [comparative]}, {}, dates)
