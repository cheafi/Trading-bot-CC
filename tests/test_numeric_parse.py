"""Tests for numeric_parse helpers."""

import unittest

from src.utils.numeric_parse import normalize_trade_plan, parse_numeric, parse_ratio


class TestNumericParse(unittest.TestCase):
    def test_parse_numeric_plain(self):
        self.assertEqual(parse_numeric(2.5), 2.5)
        self.assertEqual(parse_numeric("3"), 3.0)
        self.assertEqual(parse_numeric(None, default=-1.0), -1.0)
        self.assertEqual(parse_numeric("bad", default=0.0), 0.0)

    def test_parse_ratio_colon(self):
        self.assertEqual(parse_ratio("1:2"), 2.0)
        self.assertEqual(parse_ratio("2:3"), 1.5)
        self.assertEqual(parse_ratio("1:2.5"), 2.5)

    def test_parse_ratio_slash(self):
        self.assertEqual(parse_ratio("1/2"), 0.5)

    def test_parse_ratio_numeric(self):
        self.assertEqual(parse_ratio(2.0), 2.0)
        self.assertEqual(parse_ratio("2.5"), 2.5)
        self.assertIsNone(parse_ratio(None, default=None))
        self.assertEqual(parse_ratio("", default=0.0), 0.0)
        self.assertEqual(parse_ratio("invalid", default=0.0), 0.0)

    def test_parse_numeric_delegates_to_ratio(self):
        self.assertEqual(parse_numeric("1:2"), 2.0)

    def test_normalize_trade_plan_colon_label(self):
        tp = normalize_trade_plan({"rr_ratio_label": "1:2", "stop": 95})
        self.assertEqual(tp.get("rr_ratio"), 2.0)

    def test_normalize_trade_plan_string_ratio(self):
        tp = normalize_trade_plan({"rr_ratio": "1:2"})
        self.assertEqual(tp.get("rr_ratio"), 2.0)


if __name__ == "__main__":
    unittest.main()
