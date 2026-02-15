"""番剧搜索：按名称查全部季，返回带【第一季】等标签的 ssid 列表，便于精确定位。"""

from bilibili_api import search
from bilibili_api.search import SearchObjectType

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._common import strip_html
from panda_brain.agents.bilibili_fetcher.tools._bangumi_resolve import _collect_candidates


@bilibili_fetcher_agent.tool_plain
async def search_bangumi(keyword: str) -> str:
    """根据番剧名搜索「全部季」结果，每条带【第一季】/【第二季】/【季数未知】标签和 ssid。用户指定第几季时请选对应标签的 ssid，再 get_episode_list(ssid) 取集列表；若用户明确「第几季第几集」请优先用 resolve_bangumi_to_bvid(keyword, season, episode) 直接拿 bvid。"""
    try:
        kw = keyword.strip()
        from_s1 = await _collect_candidates(f"{kw} 第一季", from_s1_query=True)
        from_generic = await _collect_candidates(kw, from_s1_query=False)
        seen: set[int] = set()
        items: list[dict] = []
        for c in from_s1 + from_generic:
            if c["ssid"] in seen:
                continue
            seen.add(c["ssid"])
            items.append(c)
        if not items:
            return f"未找到与「{kw}」相关的结果。"
        lines: list[str] = []
        for i, c in enumerate(items[:20], 1):
            ssid = c["ssid"]
            title = strip_html(c.get("title", "未知"))
            subtitle = strip_html(c.get("subtitle", ""))
            label = c.get("season_label", "季数未知")
            line = f"{i}. 【{label}】 {title}"
            if subtitle:
                line += f"（{subtitle}）"
            line += f" — ssid: {ssid}"
            lines.append(line)
        return "搜索结果（已标季，请按用户要的「第几季」选 ssid）:\n" + "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"
