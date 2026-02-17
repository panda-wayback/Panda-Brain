"""browser_mcp 工具：直接调用 bilibili_fetcher 的解析逻辑获取播放链接，供 MCP 的 browser_navigate 使用。不经过 fetcher agent.run，减少一轮 LLM。"""

import re

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.tools.resolve import get_play_url_impl
from panda_brain.agents.browser_mcp.agent import browser_mcp_agent
from panda_brain.deps import Deps

# 用于从返回中提取纯 URL（ep 链接或 bilibili 播放页）
_URL_PATTERN = re.compile(r"https?://[^\s\u4e00-\u9fff]+", re.IGNORECASE)
_PLAY_LINK_PREFIX = "播放链接:"


@browser_mcp_agent.tool
async def get_play_url_from_fetcher(
    ctx: RunContext[Deps],
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与季/集获取该集 B 站播放链接（先查库再解析，不经过 fetcher LLM）。返回格式：第一行是纯 URL 用于 browser_navigate，第二行是说明。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名或关键词。"
    text = await get_play_url_impl(ctx.deps, keyword, season=season, episode=episode)
    text = (text or "").strip()
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
