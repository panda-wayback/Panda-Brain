from collections import defaultdict

from bilibili_api import video

from panda_brain.agents.bilibili.agent import bilibili_agent


@bilibili_agent.tool_plain
async def get_danmakus(bvid: str, limit: int = 100, from_min: float = 0, to_min: float = 6) -> str:
    """获取视频弹幕。传入 bvid，返回弹幕列表（含时间戳和文本）。limit 限制条数，from_min/to_min 为时间范围（分钟）。"""
    if limit <= 0 or limit > 500:
        limit = 100
    try:
        v = video.Video(bvid=bvid)
        # 每 6 分钟为一段，计算段范围
        from_seg = max(0, int(from_min // 6))
        to_seg = max(from_seg, int((to_min - 1) // 6))
        danmakus = await v.get_danmakus(
            page_index=0,
            from_seg=from_seg,
            to_seg=to_seg,
        )
        lines: list[str] = []
        for i, dm in enumerate(danmakus[:limit], 1):
            ts = int(dm.dm_time)
            m, s = ts // 60, ts % 60
            text = dm.text.strip().replace("\n", " ")
            lines.append(f"{i}. [{m:02d}:{s:02d}] {text[:80]}{'...' if len(text) > 80 else ''}")
        total = len(danmakus)
        head = f"弹幕（{bvid}，前{min(limit, total)}条"
        if total > limit:
            head += f"，共{total}条"
        return head + "）:\n" + "\n".join(lines) if lines else "暂无弹幕。"
    except Exception as e:
        return f"获取失败: {e}"


@bilibili_agent.tool_plain
async def analyze_danmaku_density(
    bvid: str, window_sec: int = 60, top_n: int = 5, sample_per_window: int = 3
) -> str:
    """根据弹幕密度分析视频精彩程度与各时段剧情。弹幕密度高≈观众反应强≈精彩/名场面；弹幕内容可推断剧情。
    返回：精彩时刻（高密度时段）列表、各时段剧情摘要（弹幕样本）。"""
    if window_sec < 30:
        window_sec = 60
    if top_n < 1 or top_n > 20:
        top_n = 5
    try:
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        duration = info.get("duration") or info.get("pages", [{}])[0].get("duration", 0)
        if duration <= 0:
            duration = 1500
        to_seg = max(0, int(duration / 360))
        danmakus = await v.get_danmakus(
            page_index=0,
            from_seg=0,
            to_seg=to_seg,
        )
        if not danmakus:
            return "暂无弹幕，无法分析。"
        buckets: dict[int, list[str]] = defaultdict(list)
        for dm in danmakus:
            bucket = int(dm.dm_time) // window_sec * window_sec
            text = dm.text.strip().replace("\n", " ")[:100]
            if text:
                buckets[bucket].append(text)
        density = [(b, len(buckets[b])) for b in sorted(buckets.keys())]
        density.sort(key=lambda x: -x[1])
        top_windows = density[:top_n]
        lines: list[str] = []
        lines.append(f"【精彩时刻】弹幕密度 Top{top_n}（{bvid}）")
        for i, (ts, count) in enumerate(top_windows, 1):
            m, s = ts // 60, ts % 60
            end_ts = ts + window_sec
            em, es = end_ts // 60, end_ts % 60
            samples = buckets[ts][:sample_per_window]
            desc = "；".join((s[:40] + "..." if len(s) > 40 else s) for s in samples)
            lines.append(f"  {i}. {m:02d}:{s:02d}-{em:02d}:{es:02d} 密度{count}条 | {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"分析失败: {e}"
