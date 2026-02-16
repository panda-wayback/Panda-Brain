"""bilibili_fetcher 智能体本身：配置与一次端到端对话。仅测本 agent，不测编排。"""

import asyncio
import unittest

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.deps import Deps, create_deps


class TestBilibiliFetcherAgentConfig(unittest.TestCase):
    """Agent 配置：依赖类型、流程约定在 prompt 中。"""

    def test_deps_type_is_deps(self):
        self.assertIs(bilibili_fetcher_agent.deps_type, Deps)

    def test_has_system_prompt(self):
        self.assertTrue(hasattr(bilibili_fetcher_agent, "system_prompt"))


class TestBilibiliFetcherAgentRun(unittest.TestCase):
    """Agent 一次对话：问骨王第一季第一集 bvid，应通过 resolve 得到 BV。"""

    def test_run_resolve_bvid(self):
        async def _run():
            deps = create_deps()
            result = await bilibili_fetcher_agent.run(
                "骨王第一季第一集的 bvid 是什么？请只调用 resolve_bangumi_to_bvid 得到后直接回复 bvid。",
                deps=deps,
            )
            return result.output

        output = asyncio.run(_run())
        self.assertIn("BV", output, "回复中应包含 bvid（BV 开头）")

    def test_fetch_bangumi_play_links_full_list(self):
        """提番剧名「骨王」时，fetch_bangumi_play_links 直接返回完整列表（第一季/第二季/第三季、剧场版、BVID 与链接）。"""
        from panda_brain.agents.bilibili_fetcher.tools.episode import fetch_bangumi_play_links

        async def _run():
            deps = create_deps()
            return await fetch_bangumi_play_links(deps, "骨王")

        output = asyncio.run(_run())
        self.assertIn("【第一季】", output)
        self.assertIn("【第二季】", output)
        self.assertIn("【第三季】", output)
        self.assertIn("【剧场版】", output)
        self.assertIn("BVID:", output)
        self.assertIn("链接:", output)
        # 应为几十行，不少于 30 行
        lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 30, "应输出完整播放链接列表，不得省略")
