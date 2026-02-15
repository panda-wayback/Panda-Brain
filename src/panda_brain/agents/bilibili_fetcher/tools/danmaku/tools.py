"""弹幕抓取工具：单集写入、按番剧批量写入。"""

from bilibili_api import bangumi, search
from bilibili_api.search import SearchObjectType
from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import resolve_bangumi_to_bvid as _resolve
from panda_brain.agents.bilibili_fetcher.tools._common import TABLE_DANMAKU, get_credential
from panda_brain.agents.bilibili_fetcher.tools.danmaku.store import fetch_danmaku_and_store
from panda_brain.deps import Deps


@bilibili_fetcher_agent.tool
async def fetch_and_store_danmaku(
    ctx: RunContext[Deps],
    bvid: str,
    limit: int = 0,
    summarize_with_llm: bool = False,
) -> str:
    """抓取指定 bvid 的弹幕，按秒聚合后写入 LanceDB 表 bilibili_danmaku（每秒一行，含该秒弹幕数量）。若该 bvid 已抓过则跳过。limit=0 表示不截断。summarize_with_llm=True 时用 LLM 对该秒弹幕做一句话概括（语义聚合），否则仅合并文本。"""
    bvid = (bvid or "").strip()
    if not bvid:
        return "请提供有效的 bvid（如 BV1xx）。"
    n, msg = await fetch_danmaku_and_store(
        ctx.deps, bvid, limit=limit, summarize_with_llm=summarize_with_llm
    )
    if n == 0 and msg == "已存在，跳过":
        return f"{bvid} 的弹幕已在库中，已跳过。"
    if n == 0:
        return f"{bvid}: {msg}"
    return f"{bvid}: {msg}，已写入表「{TABLE_DANMAKU}」。"


@bilibili_fetcher_agent.tool
async def fetch_danmaku_for_bangumi(
    ctx: RunContext[Deps],
    ssid: int | None = None,
    keyword: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    limit_per_ep: int = 0,
    summarize_with_llm: bool = False,
) -> str:
    """按番剧抓取弹幕，按秒聚合后写入 LanceDB。提供 ssid、或 keyword、或 keyword+season+episode（精确到某一集）。若同时提供 keyword 与 season、episode，会先按「第几季第几集」解析 bvid 再抓取该集，避免拿错季/集。limit_per_ep=0 表示不截断。"""
    cred = get_credential()
    if ssid is None and not (keyword or "").strip():
        return "请提供 ssid 或 keyword（番剧名）之一。"
    # 若指定了 keyword + season + episode，用解析逻辑拿单集 bvid，再抓取
    if (keyword or "").strip() and season is not None and episode is not None:
        bvid, _ = await _resolve(keyword.strip(), season=season, episode=episode)
        if bvid is None:
            return f"未找到「{keyword}」第{season}季第{episode}集，请检查或改用 resolve_bangumi_to_bvid 查看。"
        n, msg = await fetch_danmaku_and_store(
            ctx.deps, bvid, limit=limit_per_ep, summarize_with_llm=summarize_with_llm
        )
        if n == 0 and msg == "已存在，跳过":
            return f"{bvid}（第{season}季第{episode}集）弹幕已在库中，已跳过。"
        return f"{bvid}: {msg}"
    if ssid is None:
        try:
            result = await search.search_by_type(
                keyword=keyword.strip(),
                search_type=SearchObjectType.BANGUMI,
                page=1,
                page_size=5,
            )
            for item in result.get("result") or []:
                sid = item.get("season_id") or item.get("ssid")
                if sid:
                    ssid = sid
                    break
        except Exception as e:
            return f"搜索番剧失败: {e}"
        if ssid is None:
            return f"未找到与「{keyword}」相关的番剧。"
    try:
        s = bangumi.Bangumi(ssid=ssid, credential=cred)
        ep_data = await s.get_episode_list()
        episodes = ep_data.get("main_section", {}).get("episodes", [])
        if not episodes:
            return f"ssid {ssid} 下没有剧集。"
        bvids: list[str] = []
        for ep in episodes:
            bvid = ep.get("bvid")
            if not bvid and ep.get("id"):
                episode_obj = bangumi.Episode(epid=ep["id"], credential=cred)
                bvid = await episode_obj.get_bvid()
            if bvid:
                bvids.append(bvid)
        if not bvids:
            return "未解析到任何 bvid。"
        results: list[str] = []
        for bvid in bvids:
            n, msg = await fetch_danmaku_and_store(
                ctx.deps, bvid, limit=limit_per_ep, summarize_with_llm=summarize_with_llm
            )
            results.append(f"{bvid}: {msg}")
        return "批量抓取结果:\n" + "\n".join(results)
    except Exception as e:
        return f"批量抓取失败: {e}"
