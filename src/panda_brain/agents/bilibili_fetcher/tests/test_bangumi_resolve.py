"""测试季/集解析逻辑（_bangumi_resolve）：仅测本 agent 的解析能力，不依赖编排。"""

import unittest

from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import (
    season_label,
    season_number,
    _rank_candidates,
)


class TestSeasonLabel(unittest.TestCase):
    """季标签解析：标题/副标题 -> 【第一季】/【第二季】等。"""

    def test_first_season(self):
        self.assertEqual(season_label("OVERLORD 不死者之王 第一季", ""), "第一季")
        self.assertEqual(season_label("骨王 第1季", "副标题"), "第一季")
        self.assertEqual(season_label("某番 1期", ""), "第一季")

    def test_second_third_season(self):
        self.assertEqual(season_label("OVERLORD Ⅱ", ""), "第二季")
        self.assertEqual(season_label("OVERLORD Ⅲ", ""), "第三季")
        self.assertEqual(season_label("某番 第二季", ""), "第二季")
        self.assertEqual(season_label("某番 第3季", ""), "第三季")

    def test_roman_exclude_first(self):
        self.assertNotEqual(season_label("OVERLORD Ⅲ", ""), "第一季")
        self.assertEqual(season_label("OVERLORD Ⅲ", ""), "第三季")

    def test_unknown(self):
        self.assertEqual(season_label("未知番剧", ""), "季数未知")
        self.assertEqual(season_label("", ""), "季数未知")


class TestSeasonNumber(unittest.TestCase):
    """季数解析：标题 -> 1/2/3 或 None。"""

    def test_numeric(self):
        self.assertEqual(season_number("OVERLORD 第一季", ""), 1)
        self.assertEqual(season_number("某番 第2季", ""), 2)
        self.assertEqual(season_number("某番 第三季", ""), 3)

    def test_unknown(self):
        self.assertIsNone(season_number("未知番", ""))
        self.assertEqual(season_number("OVERLORD Ⅲ", ""), 3)


class TestRankCandidates(unittest.TestCase):
    """候选排序：目标季数匹配的排前面。"""

    def test_target_season_first(self):
        candidates = [
            {"ssid": 1, "title": "A", "season_number": 2, "from_s1_query": False},
            {"ssid": 2, "title": "B", "season_number": 1, "from_s1_query": True},
            {"ssid": 3, "title": "C", "season_number": 1, "from_s1_query": False},
        ]
        ranked = _rank_candidates(candidates, target_season=1)
        self.assertEqual(ranked[0]["season_number"], 1)
        self.assertEqual(ranked[1]["season_number"], 1)
        self.assertEqual(ranked[2]["season_number"], 2)
        self.assertTrue(ranked[0]["from_s1_query"])


if __name__ == "__main__":
    unittest.main()
