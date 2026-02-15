"""番剧季/集解析工具：根据关键词与「第几季第几集」精确定位 bvid。"""

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid as _resolve


@bilibili_fetcher_agent.tool_plain
async def resolve_bangumi_to_bvid(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与「第几季第几集」精确定位 bvid。先搜索全部结果，再按季/集筛选，避免拿错数据。返回 bvid（如 BV1xx）或错误说明。拿到 bvid 后请用 fetch_and_store_danmaku 抓取弹幕。"""
    bvid, desc = await _resolve(keyword.strip(), season=season, episode=episode)
    if bvid is None:
        return desc
    return f"bvid: {bvid}（{desc}）"
