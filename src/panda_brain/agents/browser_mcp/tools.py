"""browser_mcp 工具：向 bilibili_fetcher 获取播放链接，供 MCP 的 browser_navigate 使用。"""

import re

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher import bilibili_fetcher_agent
from panda_brain.agents.browser_mcp.agent import browser_mcp_agent
from panda_brain.deps import Deps

# 用于从 fetcher 回复中提取纯 URL（ep 链接或 bilibili 播放页）
_URL_PATTERN = re.compile(r"https?://[^\s\u4e00-\u9fff]+", re.IGNORECASE)
_PLAY_LINK_PREFIX = "播放链接:"


@browser_mcp_agent.tool
async def get_play_url_from_fetcher(
    ctx: RunContext[Deps],
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """向 bilibili_fetcher 请求该集 B 站播放链接（fetcher 会先查库再解析）。返回格式：第一行是纯 URL 用于 browser_navigate，第二行是说明。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名或关键词。"
    task = f"请返回「{keyword}」第{season}季第{episode}集的 B 站播放链接，仅第一行输出纯 URL，不要其他文字。"
    result = await bilibili_fetcher_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    text = (result.output or "").strip()
    # 先尝试「播放链接: URL」格式
    if _PLAY_LINK_PREFIX in text:
        idx = text.find(_PLAY_LINK_PREFIX)
        rest = text[idx + len(_PLAY_LINK_PREFIX) :].strip()
        url_match = _URL_PATTERN.search(rest)
        if url_match:
            return f"{url_match.group(0)}\n{text}"
    first_line = text.split("\n")[0].strip() if text else ""
    if first_line and _URL_PATTERN.fullmatch(first_line):
        return f"{first_line}\n{text}" if text != first_line else first_line
    match = _URL_PATTERN.search(text)
    if match:
        return f"{match.group(0)}\n{text}"
    return text or "未获取到播放链接。"
