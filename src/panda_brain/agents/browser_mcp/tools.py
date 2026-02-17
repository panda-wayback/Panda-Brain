"""browser_mcp 工具：解析番剧名到播放链接，供 MCP 的 browser_navigate 使用。"""

from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid
from panda_brain.agents.browser_mcp.agent import browser_mcp_agent


@browser_mcp_agent.tool_plain
async def get_bangumi_play_url(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与「第几季第几集」获取该集 B 站播放链接。未说第几季则 season=1。
    返回格式：第一行是纯 URL（仅此一行用于 browser_navigate，不要带任何中文或括号）；第二行是说明。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名或关键词。"
    bvid, play_url, desc = await resolve_bangumi_to_bvid(keyword, season=season, episode=episode)
    if bvid is None:
        return desc
    # 第一行只返回纯 URL，避免 browser_navigate 把中文描述编码进地址导致 B 站 parse failed
    return f"{play_url}\n{desc}"
