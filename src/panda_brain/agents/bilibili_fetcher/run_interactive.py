"""bilibili_fetcher 智能体交互入口：查番直接出完整列表，其余走 agent。"""

import asyncio
import logging

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.timing import timed_run
from panda_brain.agents.bilibili_fetcher.tools.episode import fetch_bangumi_play_links
from panda_brain.deps import create_deps

logging.basicConfig(level=logging.INFO, format="%(message)s")


def _is_bangumi_only_query(text: str) -> bool:
    """简单番剧名查询：短且不包含「第X季第X集」「弹幕」「bvid」等，直接拉列表并完整输出。"""
    if not text or len(text) > 40:
        return False
    t = text.strip().lower()
    if "弹幕" in t or "bvid" in t or "链接" in t:
        return False
    # 含「第N季第N集」走 agent 解析
    if "第" in text and "季" in text:
        return False
    return True


async def main():
    print("B 站抓取 agent 已启动（查番剧、拿 bvid、抓弹幕）")
    print("输入 'quit' 或 'exit' 退出\n")

    deps = create_deps()

    while True:
        try:
            user_input = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("再见!")
            break

        try:
            if _is_bangumi_only_query(user_input):
                # 番剧名直接调工具并打印完整返回，不经过模型，保证列表完整输出
                out = await timed_run("fetch_bangumi_play_links", fetch_bangumi_play_links(deps, user_input))
                print(f"\n{out}\n")
            else:
                result = await timed_run("agent.run", bilibili_fetcher_agent.run(user_input, deps=deps))
                print(f"\nAgent: {result.output}\n")
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
