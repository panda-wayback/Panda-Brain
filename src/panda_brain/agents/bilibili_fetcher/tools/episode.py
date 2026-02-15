"""番剧集列表：按 ssid 获取各集标题、BVID、播放链接。"""

from bilibili_api import bangumi

from panda_brain.agents.bilibili_fetcher.agent import bilibili_fetcher_agent
from panda_brain.agents.bilibili_fetcher.tools._common import get_credential


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
