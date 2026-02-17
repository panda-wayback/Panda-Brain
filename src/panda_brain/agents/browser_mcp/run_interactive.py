"""浏览器 MCP 智能体交互入口：多轮上下文 + Playwright MCP 工具。"""

import asyncio
import sys

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.browser_mcp import browser_mcp_agent
from panda_brain.deps import create_deps


async def main():
    print("浏览器 MCP 智能体已启动（使用 Playwright MCP 工具：打开网页、点击、快照、执行 JS）")
    print("输入例如：「骨王第十集」「从第6分钟开始播放」；多轮中「从第N分钟播放」会沿用当前已打开的页面。")
    print("输入 'quit' 或 'exit' 退出")
    print("（需 Node.js 与 npx；首次会拉取 @playwright/mcp，profile 在 ~/.config/panda_brain_browser_mcp）\n")

    deps = create_deps()
    message_history: list[ModelMessage] = []

    # 使用 async with 保持 MCP 子进程在交互期间运行，避免每次输入都起停
    async with browser_mcp_agent:
        while True:
            try:
                task = input("任务: ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not task:
                continue
            if task.lower() in ("quit", "exit"):
                print("再见!")
                break

            try:
                result = await browser_mcp_agent.run(
                    task, deps=deps, message_history=message_history
                )
                print(f"\nAgent: {result.output}\n")
                message_history = result.all_messages()
            except Exception as e:
                print(f"\n错误: {e}\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
