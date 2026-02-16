"""bilibili_fetcher 智能体响应速度与质量测试：多种查询场景，质量优先、兼顾耗时。"""

import asyncio
import re
import time
import unittest

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.deps import create_deps


def _is_single_ep_link_ok(output: str) -> tuple[bool, str]:
    """单集链接类回复：应包含 bangumi/play/ep+数字，且非错误提示。"""
    if not output or not output.strip():
        return False, "回复为空"
    if any(x in output for x in ("请提供", "无法", "无法定位", "才能查询")):
        return False, "回复为错误/索要信息"
    if "bilibili.com/bangumi/play/ep" not in output:
        return False, "未包含番剧单集播放链接"
    if not re.search(r"ep\d+", output):
        return False, "链接中无数字 ep id"
    return True, ""


def _is_full_list_ok(output: str) -> tuple[bool, str]:
    """全部链接列表：应包含季标签与链接。"""
    if not output or not output.strip():
        return False, "回复为空"
    if "【第一季】" not in output and "第一季" not in output:
        return False, "未包含季信息"
    if "链接:" not in output and "播放链接" not in output:
        return False, "未包含播放链接"
    return True, ""


async def _run_and_measure(
    user_input: str,
    deps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, float]:
    """执行一次 agent.run，返回 (output, 耗时秒)。"""
    history = message_history or []
    t0 = time.perf_counter()
    result = await bilibili_fetcher_agent.run(user_input, deps=deps, message_history=history)
    elapsed = time.perf_counter() - t0
    return result.output, elapsed


class TestBilibiliFetcherAgentLatency(unittest.TestCase):
    """多场景耗时与质量：单集、多轮上下文、不同番剧与表述，质量优先。"""

    def setUp(self):
        self.deps = create_deps()
        self.results: list[dict] = []  # 每轮 {name, output, elapsed, quality_ok, quality_msg}

    def _run_case(self, name: str, user_input: str, check_fn, history: list[ModelMessage] | None = None):
        output, elapsed = asyncio.run(_run_and_measure(user_input, self.deps, history))
        ok, msg = check_fn(output)
        self.results.append({"name": name, "output": output, "elapsed": elapsed, "ok": ok, "msg": msg})
        self.assertTrue(ok, f"{name}: 质量不通过 — {msg}")

    def test_single_ep_chinese(self):
        """单集·中文表述：骨王第三集"""
        self._run_case("单集-骨王第三集", "骨王第三集", _is_single_ep_link_ok)

    def test_single_ep_numeric(self):
        """单集·数字集数：凡人修仙传105集"""
        self._run_case("单集-凡人修仙传105集", "凡人修仙传105集", _is_single_ep_link_ok)

    def test_single_ep_explicit_season(self):
        """单集·明确季：OVERLORD 第一季第1集"""
        self._run_case("单集-OVERLORD第一季第1集", "OVERLORD 第一季第1集", _is_single_ep_link_ok)

    def test_single_ep_space_in_query(self):
        """单集·带空格：骨王 第二 集"""
        self._run_case("单集-骨王第二集带空格", "骨王 第二 集", _is_single_ep_link_ok)

    def test_context_follow_up(self):
        """多轮上下文：先骨王第三集，再只发「第四集」"""
        async def _two_turns():
            t0 = time.perf_counter()
            r1 = await bilibili_fetcher_agent.run("骨王第三集", deps=self.deps)
            t1 = time.perf_counter()
            r2 = await bilibili_fetcher_agent.run(
                "第四集", deps=self.deps, message_history=r1.all_messages()
            )
            t2 = time.perf_counter()
            return r1.output, r2.output, t1 - t0, t2 - t1

        out1, out2, t1, t2 = asyncio.run(_two_turns())
        ok1, msg1 = _is_single_ep_link_ok(out1)
        self.assertTrue(ok1, f"多轮第一轮: {msg1}")
        ok2, msg2 = _is_single_ep_link_ok(out2)
        self.results.append({
            "name": "多轮-骨王第三集后第四集",
            "output": out2,
            "elapsed": t1 + t2,
            "ok": ok2,
            "msg": msg2,
        })
        self.assertTrue(ok2, f"多轮第二轮: {msg2}")

    def test_full_list_intent(self):
        """全部链接：骨王 全部播放链接（耗时会较长，仅做质量与耗时记录）"""
        self._run_case("全部链接-骨王", "骨王 全部播放链接", _is_full_list_ok)

    def tearDown(self):
        """输出各场景耗时，便于优化；不因耗时过长失败（质量已在上方 assert）。"""
        if not self.results:
            return
        print("\n--- bilibili_fetcher 响应耗时（质量已校验通过）---")
        for r in self.results:
            t = f"{r['elapsed']:.2f}s" if r.get("elapsed") else "N/A"
            print(f"  {r['name']}: {t}")
        total = sum(x.get("elapsed") or 0 for x in self.results)
        if total > 0:
            print(f"  合计: {total:.2f}s")
        print("---\n")
