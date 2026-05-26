"""Flow follow-through calibration tests — mocked, no self_learning I/O."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.services.flow_follow_through import (
    clear_calibration_cache,
    global_calibration_summary,
    lookup_flow_follow_through,
)

_MOCK_SPARSE = {"total_records": 2, "buckets": []}

_MOCK_RICH = {
    "total_records": 42,
    "calibration_quality": 0.04,
    "buckets": [
        {
            "label": "70-80",
            "lo": 0.70,
            "hi": 0.80,
            "n": 8,
            "hit_rate": 0.625,
            "avg_forward_return_pct": 1.85,
            "avg_mae_pct": -0.9,
            "calibrated": "fair",
        }
    ],
}


class TestFlowFollowThrough(unittest.TestCase):
    def setUp(self):
        clear_calibration_cache()

    @patch("src.services.flow_follow_through._calibration_data", return_value=_MOCK_SPARSE)
    def test_insufficient_sample_honest(self, _mock_cal):
        out = lookup_flow_follow_through(radar_score=84, grade="A")
        self.assertEqual(out["basis"], "insufficient_calibration_sample")
        self.assertFalse(out["sufficient"])

    @patch("src.services.flow_follow_through._calibration_data", return_value=_MOCK_RICH)
    def test_bucket_hit_rate_when_sample_ok(self, _mock_cal):
        out = lookup_flow_follow_through(radar_score=75, grade="A")
        self.assertEqual(out["hit_rate"], 0.625)
        self.assertTrue(out["sufficient"])
        self.assertIn("Similar-confidence", out["label"])

    @patch("src.services.flow_follow_through._calibration_data", return_value=_MOCK_RICH)
    def test_global_summary_available(self, _mock_cal):
        out = global_calibration_summary()
        self.assertTrue(out["available"])
        self.assertEqual(out["total_records"], 42)


if __name__ == "__main__":
    unittest.main()
