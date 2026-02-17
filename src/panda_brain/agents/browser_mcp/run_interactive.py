"""浏览器 MCP 智能体交互入口：通过 Playwright MCP 工具（navigate/click/snapshot/evaluate）自动化浏览器。"""

import asyncio
import sys

from panda_brain.agents.browser_mcp import browser_mcp_agent
from panda_brain.deps import create_deps


async def main():
    print("浏览器 MCP 智能体已启动（使用 Playwright MCP 工具：打开网页、点击、快照、执行 JS）")
    print("输入例如：「打开 bilibili.com」「点击登录按钮」「获取页面快照」")
    print("输入 'quit' 或 'exit' 退出")
    print("（需 Node.js 与 npx；首次会拉取 @playwright/mcp，profile 在 ~/.config/panda_brain_browser_mcp）\n")

    deps = create_deps()

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
                result = await browser_mcp_agent.run(task, deps=deps)
                print(f"\nAgent: {result.output}\n")
            except Exception as e:
                print(f"\n错误: {e}\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
