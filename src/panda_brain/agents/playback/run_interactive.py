"""点播智能体交互入口：多轮上下文 + 点播记录与聊天记录写入 LanceDB。"""

import asyncio
import json
import logging
import time

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.playback import playback_agent
from panda_brain.deps import create_deps

logging.basicConfig(level=logging.INFO, format="%(message)s")

TABLE_PLAYBACK_CHAT = "playback_chat_log"


def _append_chat_log(deps, role: str, content: str):
    """将一条对话写入 LanceDB 表 playback_chat_log。"""
    ts = round(time.time(), 2)
    source = f"{role}_{ts}"
    extra = json.dumps({"role": role, "ts": ts}, ensure_ascii=False)
    deps.lancedb.add_documents(
        TABLE_PLAYBACK_CHAT,
        [{"text": content[:2000], "source": source, "extra": extra}],
    )


async def main():
    print("点播智能体已启动（说「骨王第三集」「从5分30秒播」「快进30秒」等）")
    print("输入 'quit' 或 'exit' 退出")
    print("（播放使用固定单窗口，数据在 ~/.config/panda_brain_playback；未登录 B 站时请在该窗口内登录一次即可保留大会员）\n")

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
            result = await playback_agent.run(
                user_input, deps=deps, message_history=message_history
            )
            print(f"\nAgent: {result.output}\n")
            message_history = result.all_messages()
            _append_chat_log(deps, "user", user_input)
            _append_chat_log(deps, "assistant", result.output or "")
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
