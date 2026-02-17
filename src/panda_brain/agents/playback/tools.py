"""点播工具：获取番剧播放链接、Playwright 单一窗口/标签打开与 seek、点播记录写入。"""

import json
import time

from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid
from panda_brain.agents.playback.agent import playback_agent
from panda_brain.agents.playback.playwright_driver import get_driver
from panda_brain.deps import Deps

TABLE_PLAYBACK_RECORDS = "playback_records"


@playback_agent.tool_plain
async def get_bangumi_play_url(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> str:
    """根据番剧名与「第几季第几集」获取该集播放链接（供 play 使用）。未说第几季则 season=1。返回「播放链接: URL」或错误说明。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名或关键词。"
    bvid, play_url, desc = await resolve_bangumi_to_bvid(keyword, season=season, episode=episode)
    if bvid is None:
        return desc
    return f"播放链接: {play_url}（{desc}）"


@playback_agent.tool_plain
async def play(url: str, start_time_sec: int | None = None) -> str:
    """在 Playwright 的固定单窗口单标签中打开 B 站播放链接（同一标签内跳转，不新开标签）；start_time_sec 不为空时从该秒开始播。调用后请由调用方自行 record_playback。"""
    try:
        driver = await get_driver()
        return await driver.open(url, start_time_sec=start_time_sec)
    except RuntimeError as e:
        return str(e)


@playback_agent.tool
async def seek_relative(ctx: RunContext[Deps], delta_sec: int) -> str:
    """快进或倒退若干秒。delta_sec 为正即快进，为负即倒退。通过 Playwright 控制当前播放页并写入点播记录。"""
    direction = "快进" if delta_sec > 0 else "倒退"
    abs_sec = abs(delta_sec)
    payload = {"action": "seek_relative", "ts": round(time.time(), 2), "delta_sec": delta_sec}
    ctx.deps.lancedb.add_documents(
        TABLE_PLAYBACK_RECORDS,
        [{"text": f"{direction} {abs_sec}秒", "source": f"seek_{payload['ts']}", "extra": json.dumps(payload, ensure_ascii=False)}],
    )
    try:
        driver = await get_driver()
        return await driver.seek_relative(delta_sec)
    except RuntimeError as e:
        return f"已记录；播放端未就绪: {e}"


@playback_agent.tool
async def seek_absolute(ctx: RunContext[Deps], position_sec: int) -> str:
    """跳到指定秒数位置播放。position_sec 为从片头起的秒数。通过 Playwright 控制当前播放页并写入点播记录。"""
    payload = {"action": "seek_absolute", "ts": round(time.time(), 2), "position_sec": position_sec}
    ctx.deps.lancedb.add_documents(
        TABLE_PLAYBACK_RECORDS,
        [{"text": f"跳到 {position_sec}秒", "source": f"seek_{payload['ts']}", "extra": json.dumps(payload, ensure_ascii=False)}],
    )
    try:
        driver = await get_driver()
        return await driver.seek_absolute(position_sec)
    except RuntimeError as e:
        return f"已记录；播放端未就绪: {e}"


@playback_agent.tool
async def record_playback(
    ctx: RunContext[Deps],
    action: str,
    url: str | None = None,
    keyword: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    position_sec: int | None = None,
    delta_sec: int | None = None,
) -> str:
    """写入一条点播记录，供后续习惯分析与自动点播。action 为 play / seek_relative / seek_absolute 等；其余为可选上下文。"""
    payload = {
        "action": action,
        "ts": round(time.time(), 2),
        "url": url,
        "keyword": keyword,
        "season": season,
        "episode": episode,
        "position_sec": position_sec,
        "delta_sec": delta_sec,
    }
    text = f"{action}"
    if keyword:
        text += f" {keyword}"
    if season is not None and episode is not None:
        text += f" S{season}E{episode}"
    if url:
        text += f" {url[:60]}..."
    source = f"{action}_{payload['ts']}"
    extra = json.dumps(payload, ensure_ascii=False)
    n = ctx.deps.lancedb.add_documents(
        TABLE_PLAYBACK_RECORDS,
        [{"text": text, "source": source, "extra": extra}],
    )
    return f"已写入点播记录 {n} 条。"