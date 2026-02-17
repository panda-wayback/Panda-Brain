"""测试 utils 必要逻辑：_extra。"""

import json
import unittest

from panda_brain.agents.bilibili_fetcher.utils import _extra


class TestExtra(unittest.TestCase):
    def test_dict_passthrough(self):
        self.assertEqual(_extra({"extra": {"a": 1}}), {"a": 1})

    def test_json_string(self):
        self.assertEqual(_extra({"extra": json.dumps({"play_url": "x"})}), {"play_url": "x"})

    def test_invalid_returns_empty(self):
        self.assertEqual(_extra({"extra": "not json"}), {})
        self.assertEqual(_extra({}), {})


if __name__ == "__main__":
    unittest.main()
