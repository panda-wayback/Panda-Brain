"""B 站番剧：先保证库里有该番（没有就全量拉取），再从库拿。仅保留必要逻辑。"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from bilibili_api import Credential, bangumi, search
from bilibili_api.search import SearchObjectType

from panda_brain.deps import Deps
from panda_brain.lancedb import parse_extra

# LanceDB 表名，存番剧各集的 text / source(bvid) / extra(play_url 等)
TABLE_EPISODES = "bilibili_episodes"


def get_credential() -> Credential:
    """返回 B 站 API 凭证。若环境变量 BILIBILI_SESSDATA 有值则使用，否则空凭证。"""
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()


async def _collect_candidates(keyword: str, from_s1: bool) -> list[dict[str, Any]]:
    """用 B 站搜索接口按 keyword 搜番剧，返回候选列表。
    每条候选含 ssid、season_label（用 title/subtitle 或默认「第一季」）、from_s1_query。
    供 fetch_all_and_store 合并去重后逐季拉取。"""
    out = []
    for stype in (SearchObjectType.BANGUMI, SearchObjectType.FT):
        result = await search.search_by_type(keyword=keyword, search_type=stype, page=1, page_size=20)
        for item in result.get("result") or []:
            ssid = item.get("season_id") or item.get("ssid")
            if not ssid:
                continue
            out.append({
                "ssid": ssid,
                "season_label": (item.get("title") or item.get("subtitle") or "").strip() or "第一季",
            })
    for c in out:
        c["from_s1_query"] = from_s1
    return out


def _has_anime_in_db(deps: Deps, keyword: str) -> bool:
    """库中是否已有该番：委托 LanceDB 公共 has_matching_docs。"""
    return deps.lancedb.has_matching_docs(TABLE_EPISODES, (keyword or "").strip())


async def ensure_anime_in_db(deps: Deps, keyword: str) -> None:
    """若库中尚无该番（_has_anime_in_db 为 False），则调用 fetch_all_and_store 全量拉取并写入 TABLE_EPISODES。
    tools 层在「从库拿」之前必须先调本函数，保证有数据再查。"""
    keyword = (keyword or "").strip()
    if not keyword or _has_anime_in_db(deps, keyword):
        return
    await fetch_all_and_store(deps, keyword)


def get_single_from_db(deps: Deps, keyword: str, season: int, episode: int) -> str | None:
    """在 TABLE_EPISODES 中按「keyword + 第 episode 集」语义检索，匹配 episode_index 后取 play_url。
    命中返回「播放链接: URL」及标题；未命中返回 None。"""
    try:
        for r in deps.lancedb.search(TABLE_EPISODES, f"{keyword} 第{episode}集", limit=10):
            o = parse_extra(r)
            if o.get("episode_index") != episode:
                continue
            u = o.get("play_url")
            if u and isinstance(u, str):
                return f"播放链接: {u}\n（来自库：{o.get('title') or r.get('text') or ''}）"
    except Exception:
        pass
    return None


def get_all_from_db(deps: Deps, keyword: str) -> str | None:
    """在 TABLE_EPISODES 中按 keyword 语义检索最多 200 条，拼成「【季】第N集 标题 — BVID 链接」列表字符串。
    无有效行或无 play_url 则返回 None。"""
    try:
        rows = deps.lancedb.search(TABLE_EPISODES, keyword, limit=200)
        if not rows:
            return None
        lines = []
        for r in rows:
            o = parse_extra(r)
            u = (o.get("play_url") or "").strip()
            if not u:
                continue
            lines.append(f"【{o.get('season_label') or '正片'}】第{o.get('episode_index','')}集 {o.get('title') or r.get('text','')} — {r.get('source','')} {u}")
        if not lines:
            return None
        return f"库中已有该番播放链接，共 {len(lines)} 条：\n\n" + "\n".join(lines)
    except Exception:
        return None


def _sections(ep_data: dict) -> list[tuple[str, dict]]:
    """从 B 站 get_episode_list 返回的 ep_data 中抽出 (分区名, 单集 dict) 列表。
    先遍历 main_section.episodes，再遍历 section[].episodes，用于按分区顺序且分区内重新从 1 编号。"""
    out = []
    main = ep_data.get("main_section") or {}
    for ep in main.get("episodes") or []:
        out.append((main.get("title") or "正片", ep))
    for sec in ep_data.get("section") or []:
        for ep in sec.get("episodes") or []:
            out.append((sec.get("title") or "", ep))
    return out


async def _store_ssid(deps: Deps, ssid: int, label: str, keyword: str) -> tuple[int, int, list[str]]:
    """拉取 B 站番剧某一季（ssid）的全部集数，写入 TABLE_EPISODES（已存在 bvid 则跳过）。
    label 为该季展示名（如「第一季」）。返回 (本次新增条数, 该季总集数, 用于展示的行列表)。"""
    cred = get_credential()
    s = bangumi.Bangumi(ssid=ssid, credential=cred)
    sections = _sections(await s.get_episode_list())
    if not sections:
        return 0, 0, []
    items = []
    lines_out = []
    prev_sec = None
    idx = 0
    for sec_title, ep in sections:
        if sec_title != prev_sec:
            prev_sec = sec_title
            idx = 0
        idx += 1
        title = (ep.get("share_copy") or ep.get("long_title") or ep.get("title") or "未知").strip()
        epid = ep.get("id")
        bvid = ep.get("bvid")
        if not bvid and epid:
            bvid = await bangumi.Episode(epid=epid, credential=cred).get_bvid()
        bvid = (bvid or "").strip()
        url = f"https://www.bilibili.com/bangumi/play/ep{epid}" if epid else ""
        if bvid:
            lines_out.append(f"【{label}】第{idx}集 {title} — {bvid} {url}")
        if not bvid or deps.lancedb.table_has_source(TABLE_EPISODES, bvid):
            continue
        text = f"{label} {sec_title or '正片'} 第{idx}集 {title}"
        extra = json.dumps({"source_site": "bilibili", "season_label": label, "title": title, "play_url": url, "episode_index": idx}, ensure_ascii=False)
        items.append({"text": text, "source": bvid, "extra": extra})
    if items:
        n = deps.lancedb.add_documents(TABLE_EPISODES, items)
        return n, len(sections), lines_out
    return 0, len(sections), lines_out


async def fetch_all_and_store(deps: Deps, keyword: str) -> str:
    """按番剧名全量拉取并入库：先搜「keyword 第一季」和「keyword」两路候选，按 ssid 去重后最多 20 季，
    逐季调用 _store_ssid 写 TABLE_EPISODES，最后拼成带条数/季数/集数的列表字符串返回。未找到候选则返回错误提示。"""
    a = await _collect_candidates(f"{keyword} 第一季", from_s1=True)
    b = await _collect_candidates(keyword, from_s1=False)
    seen = set()
    unique = []
    for c in a + b:
        if c["ssid"] in seen:
            continue
        seen.add(c["ssid"])
        unique.append(c)
    if not unique:
        return f"未找到与「{keyword}」相关番剧。"
    results = await asyncio.gather(*(_store_ssid(deps, c["ssid"], c.get("season_label") or "第一季", keyword) for c in unique[:20]))
    added = sum(r[0] for r in results)
    total = sum(r[1] for r in results)
    all_lines = []
    for r in results:
        all_lines.extend(r[2])
    head = f"已抓取并入库，共 {added} 条（{len(unique)} 季、{total} 集）。\n\n" if added else f"库中已有该番，共 {total} 集（{len(unique)} 季）。\n\n"
    return head + "\n".join(all_lines) if all_lines else head + "（无剧集）"
