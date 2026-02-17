"""番剧集列表：按 ssid 获取各集标题、BVID、播放链接；并可抓取全部播放链接入库。"""

import asyncio
import json

from bilibili_api import bangumi
from pydantic_ai import RunContext

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.timing import log_timing
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import _collect_candidates
from panda_brain.agents.bilibili_fetcher.tools._common import TABLE_EPISODES, get_credential
from panda_brain.deps import Deps


def _episode_list_with_sections(ep_data: dict) -> list[tuple[str, dict]]:
    """从 get_episode_list 返回中收集 (section_title, episode) 列表，保留 API 原始分区信息。"""
    out: list[tuple[str, dict]] = []
    main = ep_data.get("main_section") or {}
    for ep in main.get("episodes") or []:
        out.append((main.get("title") or "正片", ep))
    for sec in ep_data.get("section") or []:
        for ep in sec.get("episodes") or []:
            out.append((sec.get("title") or "", ep))
    return out


@log_timing("_store_ssid_episodes")
async def _store_ssid_episodes(deps: Deps, ssid: int, season_label: str) -> tuple[int, int, list[str]]:
    """拉取 ssid 对应季的各集信息并写入 bilibili_episodes 表（已存在 bvid 则跳过）。返回 (本次新增条数, 该季总集数, 该季各集用于输出的行列表)。透传 API 的 section_title、badge，不改写标签。"""
    cred = get_credential()
    s = bangumi.Bangumi(ssid=ssid, credential=cred)
    ep_data = await s.get_episode_list()
    section_episodes = _episode_list_with_sections(ep_data)
    if not section_episodes:
        return 0, 0, []
    items = []
    out_lines: list[str] = []
    # 按分区分别编号：正片第1-N集、预告第1-M集，不用全局序号（否则预告会显示成第463集等）
    prev_section: str | None = None
    idx_in_section = 0
    for section_title, ep in section_episodes:
        if section_title != prev_section:
            prev_section = section_title
            idx_in_section = 0
        idx_in_section += 1
        i = idx_in_section
        title = (ep.get("share_copy") or ep.get("long_title") or ep.get("title", "未知")).strip()
        badge = (ep.get("badge") or "").strip()
        badge_info = ep.get("badge_info") or {}
        badge_text = (badge_info.get("text") or "").strip() or badge
        epid = ep.get("id")
        bvid = ep.get("bvid")
        if not bvid and epid:
            episode_obj = bangumi.Episode(epid=epid, credential=cred)
            bvid = await episode_obj.get_bvid()
        bvid = (bvid or "").strip()
        play_url = f"https://www.bilibili.com/bangumi/play/ep{epid}" if epid else ""
        part = f"【{section_title}】" if section_title else ""
        badge_part = f" [{badge_text}]" if badge_text and badge_text != "会员" else ""
        if bvid:
            out_lines.append(f"【{season_label}】{part}第{i}集 {title}{badge_part} — BVID: {bvid} 链接: {play_url}")
        if not bvid:
            continue
        if deps.lancedb.table_has_source(TABLE_EPISODES, bvid):
            continue
        text = f"{season_label} {section_title or '正片'} 第{i}集 {title}"
        extra = json.dumps(
            {
                "source_site": "bilibili",
                "ssid": ssid,
                "season_label": season_label,
                "section_title": section_title,
                "badge": badge_text,
                "title": title,
                "play_url": play_url,
                "episode_index": i,
            },
            ensure_ascii=False,
        )
        items.append({"text": text, "source": bvid, "extra": extra})
    if items:
        n = deps.lancedb.add_documents(TABLE_EPISODES, items)
        return n, len(section_episodes), out_lines
    return 0, len(section_episodes), out_lines


async def fetch_bangumi_play_links(deps: Deps, keyword: str) -> str:
    """根据番剧名抓取该番全部季的各集播放链接并写入 LanceDB；返回完整列表文案（标题为「全片」的行已标为【剧场版】）。供交互入口直接调用，保证完整输出。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "请提供番剧名。"
    from_s1 = await _collect_candidates(f"{keyword} 第一季", from_s1_query=True)
    from_generic = await _collect_candidates(keyword, from_s1_query=False)
    seen: set[int] = set()
    unique: list[dict] = []
    for c in from_s1:
        c = {**c, "from_s1_query": True}
        if c["ssid"] in seen:
            continue
        seen.add(c["ssid"])
        unique.append(c)
    for c in from_generic:
        c = {**c, "from_s1_query": False}
        if c["ssid"] in seen:
            continue
        seen.add(c["ssid"])
        unique.append(c)
    if not unique:
        return f"未找到与「{keyword}」相关番剧。"
    async def _one(cc: dict):
        try:
            label = cc.get("season_label", "第一季")
            return await _store_ssid_episodes(deps, cc["ssid"], label)
        except Exception:
            return (0, 0, [])
    results = await asyncio.gather(*(_one(c) for c in unique[:20]))
    total_added = 0
    total_eps = 0
    all_lines: list[str] = []
    for added, count, lines in results:
        total_added += added
        total_eps += count
        all_lines.extend(lines)
    # 标题为「全片」的行标为【剧场版】，其余不改
    def _line_for_user(line: str) -> str:
        if "全片" in line and "【第一季】" in line:
            return line.replace("【第一季】", "【剧场版】", 1)
        return line
    all_lines = [_line_for_user(ln) for ln in all_lines]
    if total_added > 0:
        head = f"已抓取并入库，共 {total_added} 条播放链接（{len(unique)} 季、合计 {total_eps} 集）。以下为各季各集播放链接（供后续智能体使用）：\n\n"
    else:
        head = f"库中已有该番播放链接，共 {total_eps} 集（{len(unique)} 季）。以下为播放链接（供后续智能体使用）：\n\n"
    return head + "\n".join(all_lines) if all_lines else head + "（无剧集）"


@bilibili_fetcher_agent.tool
@log_timing("fetch_and_store_bangumi_play_links")
async def fetch_and_store_bangumi_play_links(ctx: RunContext[Deps], keyword: str) -> str:
    """根据番剧名抓取该番全部季的各集播放链接并写入 LanceDB。用户提番剧名时优先调用此工具。"""
    return await fetch_bangumi_play_links(ctx.deps, keyword)


@bilibili_fetcher_agent.tool_plain
async def get_episode_list(ssid: int | None = None) -> str:
    """根据番剧的 ssid（season_id）获取各集列表，返回每集的标题、BVID、播放链接。用于确定要抓取哪些 bvid。"""
    if ssid is None:
        return "请提供 ssid（如通过 search_bangumi 获得）。"
    cred = get_credential()
    try:
        s = bangumi.Bangumi(ssid=ssid, credential=cred)
        ep_data = await s.get_episode_list()
        episodes = ep_data.get("main_section", {}).get("episodes", [])
        if not episodes:
            return f"ssid {ssid} 下没有剧集。"
        lines: list[str] = []
        for i, ep in enumerate(episodes, 1):
            ep_title = ep.get("share_copy") or ep.get("long_title") or ep.get("title", "未知")
            epid = ep.get("id")
            bvid = ep.get("bvid")
            if not bvid and epid:
                episode_obj = bangumi.Episode(epid=epid, credential=cred)
                bvid = await episode_obj.get_bvid()
            bvid = bvid or ""
            play_url = f"https://www.bilibili.com/bangumi/play/ep{epid}" if epid else ""
            lines.append(f"{i}. {ep_title} — BVID: {bvid}" + (f" 链接: {play_url}" if play_url else ""))
        return f"番剧 ssid={ssid} 共 {len(episodes)} 集:\n" + "\n".join(lines)
    except Exception as e:
        return f"获取集列表失败: {e}"
