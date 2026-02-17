"""番剧季/集解析工具：根据关键词与「第几季第几集」精确定位 bvid；支持先查库再解析。"""

import json

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid as _resolve
from panda_brain.agents.bilibili_fetcher.tools._common import TABLE_EPISODES
from panda_brain.deps import Deps


async def get_play_url_impl(deps: Deps, keyword: str, season: int = 1, episode: int = 1) -> str:
    """根据番剧名与「第几季第几集」返回该集 B 站播放链接。先查 bilibili_episodes 表，命中则直接返回；未命中再实时解析。返回格式含「播放链接: URL」。供 bilibili_fetcher 工具与 browser_mcp 直接调用，避免多一层 agent.run。"""
    keyword = (keyword or "").strip()
    if not keyword or season < 1 or episode < 1:
        return "请提供番剧名且 season、episode 均 >= 1。"
    try:
        query = f"{keyword} 第{episode}集"
        rows = deps.lancedb.search(TABLE_EPISODES, query, limit=10)
        for r in rows:
            extra = r.get("extra")
            if not extra:
                continue
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except json.JSONDecodeError:
                    continue
            if (extra or {}).get("episode_index") == episode:
                play_url = (extra or {}).get("play_url")
                if play_url and isinstance(play_url, str):
                    title = (extra or {}).get("title") or r.get("text") or ""
                    return f"播放链接: {play_url}\n（来自库：{title}）"
    except Exception:
        pass
    bvid, play_url, desc = await _resolve(keyword, season=season, episode=episode)
    if bvid is None:
        return desc
    return f"播放链接: {play_url}\n（{desc}）" if play_url else desc


@bilibili_fetcher_agent.tool
async def get_play_url(ctx: RunContext[Deps], keyword: str, season: int = 1, episode: int = 1) -> str:
    """根据番剧名与「第几季第几集」返回该集 B 站播放链接。先查 bilibili_episodes 表，命中则直接返回；未命中再实时解析。用户要「某集链接」时请调用本工具并从返回中取出「播放链接:」后的 URL 回复。"""
    return await get_play_url_impl(ctx.deps, keyword, season=season, episode=episode)


@bilibili_fetcher_agent.tool_plain
async def resolve_bangumi_to_bvid(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与「第几季第几集」精确定位 bvid 与播放链接。season 默认 1（用户未说第几季时按第一季处理），episode 默认 1。先搜索全部结果，再按季/集筛选。返回 bvid、该集播放链接或错误说明。需要抓弹幕时用本工具取 bvid 再调用 fetch_and_store_danmaku；仅要播放链接时优先用 get_play_url（会先查库）。"""
    bvid, play_url, desc = await _resolve(keyword.strip(), season=season, episode=episode)
    if bvid is None:
        return desc
    return f"bvid: {bvid}" + (f" 播放链接: {play_url}" if play_url else "") + f"（{desc}）"
