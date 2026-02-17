"""bilibili_fetcher 智能体交互入口：全部由智能体根据用户意图选工具与回复；支持多轮上下文。"""

import asyncio
import logging

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.timing import timed_run
from panda_brain.deps import create_deps

logging.basicConfig(level=logging.INFO, format="%(message)s")

TOOL_NAME_ALL_LINKS = "fetch_and_store_bangumi_play_links"
MAGIC_OUTPUT_USE_TOOL_RESULT = "DATA_OK"


def _last_tool_result(messages: list[ModelMessage], tool_name: str) -> str | None:
    """从本轮消息中取最后一次名为 tool_name 的工具返回内容（字符串）。工具返回在 ModelRequest 的 tool-return part 里。"""
    for msg in reversed(messages):
        parts = getattr(msg, "parts", None) or []
        for p in parts:
            if (
                getattr(p, "part_kind", None) == "tool-return"
                and getattr(p, "tool_name", None) == tool_name
            ):
                content = getattr(p, "content", None)
                if isinstance(content, str) and len(content) > 50:
                    return content
    return None


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
            output = result.output or ""
            if output.strip() == MAGIC_OUTPUT_USE_TOOL_RESULT:
                tool_content = _last_tool_result(result.new_messages(), TOOL_NAME_ALL_LINKS)
                if tool_content:
                    output = tool_content
            print(f"\nAgent: {output}\n")
            message_history = result.all_messages()
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
