"""bilibili_fetcher 测试：获取数据并检查返回是否符合预期。

- TestBilibiliFetcherConfig：仅检查 agent 配置，不调模型。
- TestGetSinglePlayLink / TestGetAllPlayLinks：调用 agent 或工具获取播放链接。依赖 agent.run() 的用例在模型 502 时会跳过；直接调工具用例仅做内容断言，不依赖 LLM。
- 跳过需模型的用例：pytest -k 'not GetSingle and not GetAll' ...
"""

import asyncio
import unittest

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.config import get_model
from panda_brain.deps import Deps, create_deps

SKIP_502_MSG = "Ollama/模型不可用 (502)，跳过依赖模型的测试"


async def _llm_judge_reply(user_request: str, assistant_output: str, link_type: str) -> tuple[bool, str]:
    """用 LLM 判断助手回复是否正确提供了用户请求的 B 站播放链接。返回 (是否符合预期, 理由)。模型不可用时可能抛 ModelHTTPError。"""
    type_desc = "单集播放链接（应包含 bilibili.com/bangumi/play/ep 的链接）" if link_type == "single" else "该番剧的播放链接列表（应包含多集/多季的链接信息）"
    prompt = (
        f"用户请求：{user_request}\n\n"
        f"助手回复：\n{assistant_output}\n\n"
        f"请判断：助手回复是否正确提供了用户所请求的 {type_desc}？"
        "若回复为空、仅为错误提示、或未包含有效播放链接，则判为 NO。"
        "只回答 YES 或 NO，换行后可选一句简短原因。"
    )
    messages = [
        ModelRequest(
            parts=[
                SystemPromptPart(content="你是一个回复质量评判员。根据用户请求与助手回复，判断助手是否满足用户需求。只输出 YES/NO 及可选简短原因。"),
                UserPromptPart(content=prompt),
            ]
        )
    ]
    response = await model_request(get_model(), messages)
    if not response.parts or not hasattr(response.parts[0], "content"):
        return False, "LLM 未返回评判结果"
    raw = (response.parts[0].content or "").strip()
    reason = raw
    first_line = raw.split("\n")[0].strip().upper() if raw else ""
    ok = "YES" in first_line or "是" in raw[:20] or ("正确" in raw[:30] and "不" not in raw[:15])
    return ok, reason[:200]


class TestBilibiliFetcherConfig(unittest.TestCase):
    """Agent 配置。"""

    def test_deps_type_is_deps(self):
        self.assertIs(bilibili_fetcher_agent.deps_type, Deps)

    def test_has_system_prompt(self):
        self.assertTrue(hasattr(bilibili_fetcher_agent, "system_prompt"))


class TestGetSinglePlayLink(unittest.TestCase):
    """获取单集播放链接：输入动漫+集数，回复应包含该集 B 站播放链接，由 LLM 判断。"""

    def test_single_ep_play_link(self):
        async def _run():
            deps = create_deps()
            result = await bilibili_fetcher_agent.run(
                "骨王第一季第一集的播放链接是什么？请直接回复播放链接。",
                deps=deps,
            )
            return result.output

        try:
            output = asyncio.run(_run())
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("\n--- 用户请求：骨王第一季第一集的播放链接 ---\n助手回复：\n", output, "\n---")
        self.assertTrue(output, "回复不应为空")
        try:
            ok, reason = asyncio.run(_llm_judge_reply("骨王第一季第一集的播放链接", output, "single"))
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("LLM 判断:", "符合预期" if ok else "不符合预期", "—", reason)
        self.assertTrue(ok, f"LLM 判断回复不符合预期: {reason}")

    def test_single_ep_another_anime(self):
        """另一番剧单集：凡人修仙传第1集"""
        async def _run():
            deps = create_deps()
            result = await bilibili_fetcher_agent.run(
                "凡人修仙传第一集播放链接",
                deps=deps,
            )
            return result.output

        try:
            output = asyncio.run(_run())
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("\n--- 用户请求：凡人修仙传第一集播放链接 ---\n助手回复：\n", output, "\n---")
        self.assertTrue(output, "回复不应为空")
        try:
            ok, reason = asyncio.run(_llm_judge_reply("凡人修仙传第一集播放链接", output, "single"))
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("LLM 判断:", "符合预期" if ok else "不符合预期", "—", reason)
        self.assertTrue(ok, f"LLM 判断回复不符合预期: {reason}")


class TestGetAllPlayLinks(unittest.TestCase):
    """获取全部播放链接：输入动漫名，回复应包含该番的播放链接列表，由 LLM 判断。"""

    def test_all_links_via_agent(self):
        """通过 agent 对话要「全部链接」"""
        async def _run():
            deps = create_deps()
            result = await bilibili_fetcher_agent.run(
                "骨王 全部播放链接，请给我完整列表。",
                deps=deps,
            )
            return result.output

        try:
            output = asyncio.run(_run())
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("\n--- 用户请求：骨王 全部播放链接 ---\n助手回复：\n", output, "\n---")
        self.assertTrue(output, "回复不应为空")
        try:
            ok, reason = asyncio.run(_llm_judge_reply("骨王 全部播放链接", output, "all"))
        except ModelHTTPError as e:
            if e.status_code == 502:
                self.skipTest(SKIP_502_MSG)
            raise
        print("LLM 判断:", "符合预期" if ok else "不符合预期", "—", reason)
        self.assertTrue(ok, f"LLM 判断回复不符合预期: {reason}")

    def test_all_links_direct_tool(self):
        """直接调用 fetch 工具，检查返回是否包含季与链接信息（不依赖 LLM）"""
        async def _run():
            from panda_brain.agents.bilibili_fetcher.tools.episode import fetch_bangumi_play_links
            deps = create_deps()
            return await fetch_bangumi_play_links(deps, "骨王")

        output = asyncio.run(_run())
        print("\n--- 直接调工具 fetch_bangumi_play_links(骨王) ---\n返回：\n", output, "\n---")
        self.assertTrue(output, "工具返回不应为空")
        self.assertIn("链接", output, "应包含链接信息")
        self.assertIn("bilibili.com", output, "应包含 B 站播放链接")
        self.assertIn("【", output, "应包含季/集信息（如【第一季】）")
        self.assertRegex(output, r"\d+\s*条", msg="应包含条数（如 N 条）")


if __name__ == "__main__":
    unittest.main()
