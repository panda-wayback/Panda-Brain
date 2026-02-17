"""全部链接。设计：先保证库里有该番（没有就全量拉取）→ 从库拿 → 返回。逻辑在 utils。"""

import logging

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.timing import log_timing
from panda_brain.agents.bilibili_fetcher.utils import (
    ensure_anime_in_db,
    get_all_from_db,
)
from panda_brain.deps import Deps

logger = logging.getLogger(__name__)


async def fetch_bangumi_play_links(deps: Deps, keyword: str) -> str:
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名。"
    logger.info("[获取链接] 工具入参 keyword=%r", keyword)
    await ensure_anime_in_db(deps, keyword)
    out = get_all_from_db(deps, keyword)
    result = out or "未找到该番剧相关链接。"
    logger.info("[获取链接] 工具返回: %d 字符, %d 行", len(result), result.count("\n") + 1)
    return result


@bilibili_fetcher_agent.tool
@log_timing("fetch_and_store_bangumi_play_links")
async def fetch_and_store_bangumi_play_links(ctx: RunContext[Deps], keyword: str) -> str:
    """根据番剧名抓取该番全部季的各集播放链接并写入 LanceDB。先保证向量库有该番数据（没有则全量拉取），再从库返回。用户要「全部链接」「链接列表」时调用此工具。"""
    return await fetch_bangumi_play_links(ctx.deps, keyword)
