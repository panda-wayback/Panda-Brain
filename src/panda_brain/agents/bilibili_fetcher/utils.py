"""B 站番剧：先保证库里有该番（没有就全量拉取），再从库拿。仅保留必要逻辑。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


def _strip_html(s: str) -> str:
    """去掉 B 站 API 可能返回的 HTML 高亮标签（如 <em class="keyword">），只保留纯文本。"""
    if not s:
        return s
    return re.sub(r"<[^>]+>", "", s).strip()

from bilibili_api import Credential, bangumi, search
from bilibili_api.search import SearchObjectType

from panda_brain.deps import Deps
from panda_brain.lancedb import parse_extra

# LanceDB 表名
TABLE_EPISODES = "bilibili_episodes"  # 番剧各集的 text / source(bvid) / extra(play_url 等)
TABLE_ANIME_ALIASES = "bilibili_anime_aliases"  # 番剧别名/同一作品：keyword + 库中季标题，供智能体判断


def get_credential() -> Credential:
    """返回 B 站 API 凭证。若环境变量 BILIBILI_SESSDATA 有值则使用，否则空凭证。"""
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()


async def _collect_candidates(keyword: str, from_s1: bool) -> list[dict[str, Any]]:
    """用 B 站搜索接口按 keyword 搜番剧，返回候选列表。
    每条候选含 ssid、season_label、title、subtitle（供后续写入别名表时汇总番剧的多种名称）。
    供 fetch_all_and_store 合并去重后逐季拉取。"""
    out = []
    for stype in (SearchObjectType.BANGUMI, SearchObjectType.FT):
        result = await search.search_by_type(keyword=keyword, search_type=stype, page=1, page_size=20)
        for item in result.get("result") or []:
            ssid = item.get("season_id") or item.get("ssid")
            if not ssid:
                continue
            title = _strip_html((item.get("title") or "").strip())
            subtitle = _strip_html((item.get("subtitle") or "").strip())
            out.append({
                "ssid": ssid,
                "season_label": (title or subtitle or "第一季"),
                "title": title,
                "subtitle": subtitle,
            })
    for c in out:
        c["from_s1_query"] = from_s1
    return out


def _has_anime_in_db(deps: Deps, keyword: str) -> bool:
    """库中是否已有该番：语义检索后只保留 text 含 keyword 的文档，避免把其它番当成已有。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return False
    rows = deps.lancedb.search(TABLE_EPISODES, keyword, limit=50)
    matched = [r for r in rows if keyword in (r.get("text") or "")]
    return len(matched) >= 1


async def ensure_anime_in_db(deps: Deps, keyword: str) -> None:
    """若库中尚无该番（_has_anime_in_db 为 False），则调用 fetch_all_and_store 全量拉取并写入 TABLE_EPISODES。
    tools 层在「从库拿」之前必须先调本函数，保证有数据再查。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return
    if _has_anime_in_db(deps, keyword):
        logger.info("[获取链接] 库中已有「%s」，跳过拉取", keyword)
        return
    logger.info("[获取链接] 开始拉取「%s」播放链接", keyword)
    await fetch_all_and_store(deps, keyword)


def get_single_from_db(deps: Deps, keyword: str, season: int, episode: int) -> str | None:
    """在 TABLE_EPISODES 中按「keyword + 第 episode 集」语义检索，匹配 episode_index 后取 play_url。
    只考虑 text 含 keyword 的文档，避免命中其它番。命中返回「播放链接: URL」及标题；未命中返回 None。"""
    try:
        keyword = (keyword or "").strip()
        for r in deps.lancedb.search(TABLE_EPISODES, f"{keyword} 第{episode}集", limit=20):
            if keyword not in (r.get("text") or ""):
                continue
            o = parse_extra(r)
            if o.get("episode_index") != episode:
                continue
            u = o.get("play_url")
            if u and isinstance(u, str):
                raw = o.get("title") or r.get("text") or ""
                return f"播放链接: {u}\n（来自库：{_strip_html(raw)}）"
    except Exception:
        pass
    return None


def _alias_note_from_db(deps: Deps, keyword: str, link_output: str) -> str:
    """从 TABLE_ANIME_ALIASES 查 keyword 的别名/同一作品说明；若返回的链接里含库中季标题且与 keyword 不同，则返回说明供智能体判断。"""
    try:
        rows = deps.lancedb.search(TABLE_ANIME_ALIASES, keyword, limit=3)
        for r in rows:
            if keyword not in (r.get("text") or ""):
                continue
            o = parse_extra(r)
            labels = o.get("labels") or []
            aliases = o.get("aliases") or labels or []
            # link_output 已去 HTML，用去 HTML 后的 label 做匹配
            others = [lb for lb in labels if lb and _strip_html(lb) != keyword and _strip_html(lb) in link_output]
            if not others:
                continue
            others_clean = [_strip_html(lb) for lb in others[:5]]
            aliases_clean = [_strip_html(a) for a in list(aliases)[:8]] if aliases else []
            note = f"\n\n（库中季标题为「{'」「'.join(others_clean)}」等，与「{keyword}」为同一作品。"
            if aliases_clean:
                note += f" 该番剧在库中的名称/别名：{', '.join(aliases_clean)}。"
            note += "）"
            return note
    except Exception:
        pass
    return ""


def get_all_from_db(deps: Deps, keyword: str) -> str | None:
    """在 TABLE_EPISODES 中按 keyword 语义检索，只保留 text 含 keyword 的文档（避免混入其它番），
    按季+集数排序后拼成「【季】第N集 标题 — BVID 链接」列表；并从 TABLE_ANIME_ALIASES 附带同一作品说明（若有）。无有效行或无 play_url 则返回 None。"""
    try:
        keyword = (keyword or "").strip()
        # 单番剧集数有限（通常几十到几百），用较大 limit 尽量一次取全，避免向量检索截断
        rows = deps.lancedb.search(TABLE_EPISODES, keyword, limit=10000)
        rows = [r for r in rows if keyword in (r.get("text") or "")]
        if not rows:
            logger.info("[获取链接] 从库读取「%s」: 0 条（过滤后）", keyword)
            return None
        # 按季标题、集数排序，保证展示顺序为第1季第1集…第1季第N集、第2季第1集…
        def _sort_key(r):
            o = parse_extra(r)
            return (str(o.get("season_label") or "正片"), int(o.get("episode_index") or 0))
        rows.sort(key=_sort_key)
        lines = []
        for r in rows:
            o = parse_extra(r)
            u = (o.get("play_url") or "").strip()
            if not u:
                continue
            label = _strip_html(str(o.get("season_label") or "正片"))
            title = _strip_html(str(o.get("title") or r.get("text") or ""))
            lines.append(f"【{label}】第{o.get('episode_index','')}集 {title} — {r.get('source','')} {u}")
        if not lines:
            logger.info("[获取链接] 从库读取「%s」: 检索 %d 条但无有效 play_url", keyword, len(rows))
            return None
        out = f"库中已有该番播放链接，共 {len(lines)} 条：\n\n" + "\n".join(lines)
        # 兜底：整段去掉 HTML 标签（不 strip 首尾），避免库里历史数据仍带 <em> 等
        if out and "<" in out and ">" in out:
            out = re.sub(r"<[^>]+>", "", out)
        note = _alias_note_from_db(deps, keyword, out)
        if not note:
            # 已有数据可能未写过别名：用本次结果的季标题回写一条（仅当别名表尚无该 keyword 时）
            labels = list({(parse_extra(r).get("season_label") or "正片").strip() for r in rows})
            others = [lb for lb in labels if lb and lb != keyword]
            if others:
                alias_rows = deps.lancedb.search(TABLE_ANIME_ALIASES, keyword, limit=1)
                if not any(keyword in (r.get("text") or "") for r in alias_rows):
                    names = {keyword} | set(_strip_html(lb) for lb in labels)
                    alias_text = f"{' '.join(names)} 同一番剧 别名 库中季标题 番剧名"
                    alias_extra = json.dumps({"keyword": keyword, "labels": labels, "aliases": list(names)}, ensure_ascii=False)
                    deps.lancedb.add_documents(TABLE_ANIME_ALIASES, [{"text": alias_text, "source": f"alias:{keyword}", "extra": alias_extra}])
                note = f"\n\n（库中季标题为「{'」「'.join(_strip_html(lb) for lb in others[:5])}」等，与「{keyword}」为同一作品。）"
        out += note
        if "<" in out and ">" in out:
            out = re.sub(r"<[^>]+>", "", out)
        logger.info("[获取链接] 从库读取「%s」: 共 %d 条, 返回文本 %d 字符", keyword, len(lines), len(out))
        return out
    except Exception as e:
        logger.exception("[获取链接] 从库读取「%s」异常: %s", keyword, e)
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
    label = _strip_html(label)
    cred = get_credential()
    s = bangumi.Bangumi(ssid=ssid, credential=cred)
    sections = _sections(await s.get_episode_list())
    logger.info("[获取链接] 季 ssid=%s label=%s 本季 %d 个分区", ssid, label, len(sections))
    if not sections:
        return 0, 0, []
    items = []
    lines_out = []
    prev_sec = None
    idx = 0
    for sec_title, ep in sections:
        sec_title = _strip_html(sec_title or "")
        if sec_title != prev_sec:
            prev_sec = sec_title
            idx = 0
        idx += 1
        title = _strip_html((ep.get("share_copy") or ep.get("long_title") or ep.get("title") or "未知").strip())
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
        text = f"{keyword} {label} {sec_title or '正片'} 第{idx}集 {title}"
        extra = json.dumps({"source_site": "bilibili", "anime_name": keyword, "season_label": label, "title": title, "play_url": url, "episode_index": idx}, ensure_ascii=False)
        items.append({"text": text, "source": bvid, "extra": extra})
    if items:
        n = deps.lancedb.add_documents(TABLE_EPISODES, items)
        logger.info("[获取链接] 季 ssid=%s 入库 %d 条（本季展示 %d 行）", ssid, n, len(lines_out))
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
        logger.warning("[获取链接] 「%s」未找到番剧候选", keyword)
        return f"未找到与「{keyword}」相关番剧。"
    logger.info("[获取链接] 「%s」候选 %d 季，开始逐季拉取", keyword, len(unique[:20]))
    results = await asyncio.gather(*(_store_ssid(deps, c["ssid"], c.get("season_label") or "第一季", keyword) for c in unique[:20]))
    added = sum(r[0] for r in results)
    total = sum(r[1] for r in results)
    all_lines = []
    for r in results:
        all_lines.extend(r[2])
    logger.info("[获取链接] 「%s」拉取完成：本次新增 %d 条，共 %d 集 %d 季，返回 %d 行", keyword, added, total, len(unique[:20]), len(all_lines))
    # 写入番剧别名等信息到向量库：用户 keyword、库中季标题、搜索得到的 title/subtitle，便于智能体判断同一作品
    labels = list({(c.get("season_label") or "第一季").strip() for c in unique[:20] if (c.get("season_label") or "").strip()})
    names = {keyword.strip()}
    for c in unique[:20]:
        for k in ("season_label", "title", "subtitle"):
            v = (c.get(k) or "").strip()
            if v:
                names.add(v)
    if names:
        alias_text = f"{' '.join(names)} 同一番剧 别名 库中季标题 番剧名"
        alias_extra = json.dumps({"keyword": keyword, "labels": labels, "aliases": list(names)}, ensure_ascii=False)
        deps.lancedb.add_documents(TABLE_ANIME_ALIASES, [{"text": alias_text, "source": f"alias:{keyword}", "extra": alias_extra}])
    head = f"已抓取并入库，共 {added} 条（{len(unique)} 季、{total} 集）。\n\n" if added else f"库中已有该番，共 {total} 集（{len(unique)} 季）。\n\n"
    return head + "\n".join(all_lines) if all_lines else head + "（无剧集）"
