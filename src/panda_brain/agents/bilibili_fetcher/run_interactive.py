"""bilibili_fetcher 智能体交互入口：全部由智能体根据用户意图选工具与回复；支持多轮上下文。"""

import asyncio
import logging

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.timing import timed_run
from panda_brain.deps import create_deps

logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main():
    print("B 站抓取 agent 已启动（查番剧、拿 bvid、抓弹幕）")
    print("输入 'quit' 或 'exit' 退出\n")

    deps = create_deps()
    message_history: list[ModelMessage] = []

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
            result = await timed_run(
                "agent.run",
                bilibili_fetcher_agent.run(user_input, deps=deps, message_history=message_history),
            )
            print(f"\nAgent: {result.output}\n")
            message_history = result.all_messages()
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
