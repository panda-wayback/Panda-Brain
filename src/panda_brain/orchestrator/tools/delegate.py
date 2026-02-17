"""编排器工具：委托给子 Agent（bilibili_fetcher、browser_mcp）。"""

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.agents.browser_mcp import browser_mcp_agent
from panda_brain.deps import Deps
from panda_brain.orchestrator.agent import orchestrator


@orchestrator.tool
async def delegate_to_bilibili_fetcher(ctx: RunContext[Deps], task: str) -> str:
    """将 B 站数据抓取任务（按番剧名查找动漫、抓取弹幕并写入 LanceDB，避免重复抓取）委托给抓取专家 Agent。"""
    result = await bilibili_fetcher_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    return result.output


@orchestrator.tool
async def delegate_to_browser_mcp(ctx: RunContext[Deps], task: str) -> str:
    """将通用浏览器自动化任务（打开网页、点击、填表、截图、执行 JS 等）委托给浏览器 MCP 智能体（基于 Playwright MCP）。"""
    result = await browser_mcp_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    return result.output
