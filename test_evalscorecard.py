"""evalscorecard —— 自检测试。

把多次评测的样本级结果聚合成记分卡，逐指标列出均值、离散度与回归项。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import evalscorecard  # noqa: E402


class TestEvalScorecard(unittest.TestCase):
    def test_regression_is_detected_and_ranked_first(self):
        current = {"acc": [0.9, 0.9, 0.9], "f1": [0.5, 0.5, 0.5]}
        baseline = {"acc": [0.9, 0.9, 0.9], "f1": [0.8, 0.8, 0.8]}
        card = evalscorecard.compare(current, baseline, 1e-9)
        self.assertEqual(len(card["regressions"]), 1)
        self.assertEqual(card["regressions"][0]["metric"], "f1")
        self.assertEqual(card["rows"][0]["metric"], "f1")

    def test_flat_total_hides_regression(self):
        """总分不变但有指标回退——这正是这个工具存在的理由。"""
        current = {"a": [0.8], "b": [0.8]}
        baseline = {"a": [0.9], "b": [0.7]}
        card = evalscorecard.compare(current, baseline, 1e-9)
        self.assertAlmostEqual(card["overall"]["current"], 0.8)
        self.assertAlmostEqual(card["overall"]["baseline"], 0.8)
        self.assertEqual(len(card["regressions"]), 1)
        self.assertEqual(len(card["improvements"]), 1)

    def test_std_is_reported(self):
        card = evalscorecard.compare({"a": [0.5, 0.9, 0.7]}, None, 1e-9)
        self.assertIsNotNone(card["rows"][0]["current"]["std"])

    def test_lower_is_better_direction(self):
        current = {"latency": {"scores": [10.0], "higher_is_better": False}}
        baseline = {"latency": {"scores": [20.0], "higher_is_better": False}}
        card = evalscorecard.compare(current, baseline, 1e-9)
        self.assertEqual(card["rows"][0]["direction"], "up")

    def test_new_metric_is_flagged(self):
        card = evalscorecard.compare({"a": [1.0], "b": [1.0]}, {"a": [1.0]}, 1e-9)
        row = [r for r in card["rows"] if r["metric"] == "b"][0]
        self.assertTrue(row["new_metric"])
