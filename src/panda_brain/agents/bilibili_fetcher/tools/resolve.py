"""单集链接。设计：先保证库里有该番（没有就全量拉取）→ 从库拿 → 返回。逻辑在 utils。"""

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.utils import (
    ensure_anime_in_db,
    get_single_from_db,
)
from panda_brain.deps import Deps


async def get_play_url_impl(deps: Deps, keyword: str, season: int = 1, episode: int = 1) -> str:
    keyword = (keyword or "").strip()
    if not keyword or season < 1 or episode < 1:
        return "请提供番剧名且 season、episode 均 >= 1。"
    await ensure_anime_in_db(deps, keyword)
    out = get_single_from_db(deps, keyword, season, episode)
    return out or "未找到该季该集，请确认季/集数。"


@bilibili_fetcher_agent.tool
async def get_play_url(ctx: RunContext[Deps], keyword: str, season: int = 1, episode: int = 1) -> str:
    """根据番剧名与「第几季第几集」返回该集 B 站播放链接。先保证向量库有该番数据（没有则全量拉取），再从库返回。用户要「某集链接」时请调用本工具并从返回中取出「播放链接:」后的 URL 回复。"""
    return await get_play_url_impl(ctx.deps, keyword, season=season, episode=episode)
