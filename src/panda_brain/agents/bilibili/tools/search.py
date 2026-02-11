import re

from bilibili_api import search
from bilibili_api.search import SearchObjectType

from panda_brain.agents.bilibili.agent import bilibili_agent


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s) if s else ""


@bilibili_agent.tool_plain
async def search_bangumi_ssid(keyword: str) -> str:
    """根据番剧/影视名称搜索，返回匹配的 ssid（season_id）、media_id、标题等。同时搜索番剧和影视类型（含剧场版）。"""
    try:
        seen_ssid: set[int] = set()
        items: list[dict] = []
        for stype in (SearchObjectType.BANGUMI, SearchObjectType.FT):
            result = await search.search_by_type(
                keyword=keyword,
                search_type=stype,
                page=1,
                page_size=10,
            )
            for item in result.get("result") or []:
                sid = item.get("season_id") or item.get("ssid")
                if sid and sid not in seen_ssid:
                    seen_ssid.add(sid)
                    items.append(item)
        if not items:
            return f"未找到与「{keyword}」相关的结果。"
        lines: list[str] = []
        for i, item in enumerate(items[:15], 1):
            ssid = item.get("season_id") or item.get("ssid")
            media_id = item.get("media_id")
            title = _strip_html(item.get("title", "未知"))
            subtitle = _strip_html(item.get("subtitle", ""))
            season_name = item.get("season_type_name", "")
            line = f"{i}. {title}"
            if season_name:
                line += f"（{season_name}）"
            elif subtitle:
                line += f"（{subtitle}）"
            line += f" — ssid: {ssid}"
            if media_id:
                line += f", media_id: {media_id}"
            lines.append(line)
        return "搜索结果（番剧+影视/剧场版）:\n" + "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"
