"""番剧季/集解析工具：根据关键词与「第几季第几集」精确定位 bvid。"""

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid as _resolve


@bilibili_fetcher_agent.tool_plain
async def resolve_bangumi_to_bvid(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与「第几季第几集」精确定位 bvid 与播放链接。season 默认 1（用户未说第几季时按第一季处理），episode 默认 1。先搜索全部结果，再按季/集筛选。返回 bvid、该集播放链接或错误说明。用户要「某集链接」时请直接回复工具返回的播放链接；要抓弹幕时用 bvid 调用 fetch_and_store_danmaku。"""
    bvid, play_url, desc = await _resolve(keyword.strip(), season=season, episode=episode)
    if bvid is None:
        return desc
    return f"bvid: {bvid}" + (f" 播放链接: {play_url}" if play_url else "") + f"（{desc}）"
