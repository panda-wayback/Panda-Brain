"""番剧季/集解析：先搜索全部结果，再按「第几季第几集」精确定位 bvid。供工具与测试共用。"""

from __future__ import annotations

import re
from typing import Any

from bilibili_api import bangumi, search
from bilibili_api.search import SearchObjectType


# 季数在标题中的匹配：第一季/第1季/1期 等；排除 第二季/Ⅲ 等
_SEASON_PATTERN = re.compile(
    r"(?:第一季|第1季|1期)|(?:第二季|第2季|2期)|(?:第三季|第3季|3期)|(?:第四季|第4季|4期)|(?:第五季|第5季|5期)"
)
_ROMAN_EXCLUDE = re.compile(r"[ⅡⅢⅣⅴⅵⅱⅲⅳⅵ]")  # 罗马数字 2–6，排除误判第一季


def season_label(title: str, subtitle: str) -> str:
    """从标题/副标题解析季标签，返回「第一季」「第二季」「第三季」或「季数未知」。"""
    t = (title or "") + " " + (subtitle or "")
    if _ROMAN_EXCLUDE.search(t):
        if "第三" in t or "第3" in t or "Ⅲ" in t:
            return "第三季"
        if "第二" in t or "第2" in t or "Ⅱ" in t:
            return "第二季"
        if "第四" in t or "第4" in t:
            return "第四季"
    m = _SEASON_PATTERN.search(t)
    if m:
        g = m.group(0)
        if "一" in g or "1" in g:
            return "第一季"
        if "二" in g or "2" in g:
            return "第二季"
        if "三" in g or "3" in g:
            return "第三季"
        if "四" in g or "4" in g:
            return "第四季"
        if "五" in g or "5" in g:
            return "第五季"
    return "季数未知"


def season_number(title: str, subtitle: str) -> int | None:
    """从标题解析季数 1–5，无法判断则返回 None。"""
    label = season_label(title, subtitle)
    if label == "第一季":
        return 1
    if label == "第二季":
        return 2
    if label == "第三季":
        return 3
    if label == "第四季":
        return 4
    if label == "第五季":
        return 5
    return None


async def _collect_candidates(keyword: str, from_s1_query: bool = False) -> list[dict[str, Any]]:
    """搜索番剧，收集 ssid、标题、季标签。"""
    candidates: list[dict[str, Any]] = []
    for stype in (SearchObjectType.BANGUMI, SearchObjectType.FT):
        result = await search.search_by_type(
            keyword=keyword,
            search_type=stype,
            page=1,
            page_size=20,
        )
        for item in (result.get("result") or []):
            ssid = item.get("season_id") or item.get("ssid")
            if not ssid:
                continue
            title = (item.get("title") or "").strip()
            subtitle = (item.get("subtitle") or "").strip()
            label = season_label(title, subtitle)
            num = season_number(title, subtitle)
            candidates.append({
                "ssid": ssid,
                "title": title,
                "subtitle": subtitle,
                "season_label": label,
                "season_number": num,
                "from_s1_query": from_s1_query,
            })
    return candidates


def _rank_candidates(candidates: list[dict], target_season: int) -> list[dict]:
    """按目标季数排序：匹配目标季的优先，且来自「第一季」搜索的优先（当目标为 1 时）。"""
    def key(c: dict) -> tuple[int, int, str]:
        match = 0 if c.get("season_number") == target_season else 1
        from_s1 = 0 if (target_season == 1 and c.get("from_s1_query")) else 1
        return match, from_s1, c.get("title", "")
    return sorted(candidates, key=key)


async def resolve_bangumi_to_bvid(
    keyword: str,
    season: int = 1,
    episode: int = 1,
) -> tuple[str | None, str]:
    """
    先搜索全部番剧结果，再按「第 season 季、第 episode 集」定位，返回对应 bvid。
    返回 (bvid, 描述)；未找到时 bvid 为 None，描述为错误说明。
    """
    if season < 1 or episode < 1:
        return None, "season 与 episode 均须 >= 1"
    s1_query = f"{keyword} 第一季" if season == 1 else keyword
    from_s1 = await _collect_candidates(s1_query, from_s1_query=(season == 1))
    from_generic = await _collect_candidates(keyword, from_s1_query=False)
    seen: set[int] = set()
    candidates: list[dict] = []
    for c in from_s1 + from_generic:
        if c["ssid"] in seen:
            continue
        seen.add(c["ssid"])
        candidates.append(c)
    candidates = _rank_candidates(candidates, target_season=season)
    # 先尝试明确匹配目标季的候选
    to_try = [c for c in candidates if c.get("season_number") == season]
    # 第一季时：若没有标题带「第一季」的，则把「季数未知」且来自「关键词 第一季」搜索的当作第一季
    if season == 1 and not to_try:
        to_try = [c for c in candidates if c.get("season_number") is None and c.get("from_s1_query")]
    if season == 1 and not to_try:
        to_try = [c for c in candidates if c.get("season_number") is None][:3]
    for c in to_try:
        ssid = c["ssid"]
        try:
            s = bangumi.Bangumi(ssid=ssid)
            ep_data = await s.get_episode_list()
            episodes = ep_data.get("main_section", {}).get("episodes", [])
            if not episodes:
                continue
            idx = episode - 1
            if idx >= len(episodes):
                continue
            ep = episodes[idx]
            bvid = ep.get("bvid")
            if not bvid and ep.get("id"):
                ep_obj = bangumi.Episode(epid=ep["id"])
                bvid = await ep_obj.get_bvid()
            if bvid:
                desc = f"第{season}季 第{episode}集（ssid={ssid}, {c['title'][:40]}）"
                return bvid, desc
        except Exception:
            continue
    return None, f"未找到「{keyword}」第{season}季第{episode}集对应的 bvid，请确认季/集或改用 search_bangumi 查看全部结果。"
