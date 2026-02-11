import os

from bilibili_api import Credential, bangumi

from panda_brain.agents.bilibili.agent import bilibili_agent


def _get_credential() -> Credential:
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()


@bilibili_agent.tool_plain
async def get_bangumi_playback_links(ssid: int | None = None, media_id: int | None = None) -> str:
    """获取番剧各集的 B 站网页播放链接。传入 ssid（season_id，推荐）或 media_id 之一。返回每集的标题、BVID 和播放链接。"""
    if ssid is None and media_id is None:
        return "错误：请提供 ssid 或 media_id 之一。"
    cred = _get_credential()
    lines: list[str] = []
    try:
        if ssid is not None:
            seasons = [{"season_id": ssid, "season_title": f"季{ssid}"}]
        else:
            m = bangumi.Bangumi(media_id=media_id, credential=cred)
            info = await m.get_meta()
            media_info = info.get("media", {})
            title = media_info.get("title", "未知")
            seasons = media_info.get("seasons", [])
            if not seasons:
                seasons = [{"season_id": await m.get_season_id(), "season_title": title}]

        for s_info in seasons:
            sid = s_info["season_id"]
            s_title = s_info.get("season_title") or s_info.get("title", f"第{sid}季")
            lines.append(f"\n--- {s_title} (ID: {sid}) ---")

            s = bangumi.Bangumi(ssid=sid, credential=cred)
            ep_data = await s.get_episode_list()
            episodes = ep_data.get("main_section", {}).get("episodes", [])

            for ep in episodes:
                ep_title = ep.get("share_copy") or ep.get("long_title") or ep.get("title", "未知")
                epid = ep["id"]
                play_url = f"https://www.bilibili.com/bangumi/play/ep{epid}"
                bvid = ep.get("bvid")
                if not bvid:
                    episode_obj = bangumi.Episode(epid=epid, credential=cred)
                    bvid = await episode_obj.get_bvid()
                bvid = bvid or ""
                lines.append(f"集数: {ep_title}\nBVID: {bvid}\n播放链接: {play_url}")

        return "🎬 番剧播放链接:\n" + "\n".join(lines) if lines else "未找到剧集。"
    except Exception as e:
        return f"获取失败: {e}"
