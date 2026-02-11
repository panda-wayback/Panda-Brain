"""弹幕相关 tool_plain 注册入口。"""

import os
from collections import defaultdict

from bilibili_api import Credential, video
from bilibili_api import comment as comment_api
from bilibili_api.comment import CommentResourceType, OrderType
from bilibili_api.utils.aid_bvid_transformer import bvid2aid

from panda_brain.agents.bilibili.agent import bilibili_agent
from panda_brain.agents.bilibili.tools.danmaku._internal.density import sliding_density, smooth
from panda_brain.agents.bilibili.tools.danmaku._internal.segment import select_boundaries
from panda_brain.agents.bilibili.tools.danmaku._internal.utils import (
    fmt_ts,
    heat_label,
    segment_samples,
)


async def _fetch_top_comments(bvid: str, top_n: int = 15) -> list[dict]:
    """获取高赞评论，失败返回空列表（不影响主体分析）。"""
    try:
        sessdata = os.environ.get("BILIBILI_SESSDATA", "")
        cred = Credential(sessdata=sessdata) if sessdata else Credential()
        aid = bvid2aid(bvid)
        result = await comment_api.get_comments(
            oid=aid, type_=CommentResourceType.VIDEO,
            page_index=1, order=OrderType.LIKE, credential=cred,
        )
        comments: list[dict] = []
        for r in (result.get("replies") or [])[:top_n]:
            msg = (r.get("content") or {}).get("message", "").strip()
            like = r.get("like", 0)
            if msg:
                comments.append({"text": msg[:200], "like": like})
        return comments
    except Exception:
        return []


def _trigrams(text: str) -> set[str]:
    """提取字符 trigram 集合。"""
    return {text[i: i + 3] for i in range(len(text) - 2)} if len(text) >= 3 else set()


def _match_comments_to_segment(
    comments: list[dict], seg_text: str, max_match: int = 2,
) -> list[dict]:
    """用 trigram 重叠找与该段弹幕内容相关的评论。"""
    seg_grams = _trigrams(seg_text)
    if not seg_grams:
        return []
    scored: list[tuple[float, dict]] = []
    for c in comments:
        c_grams = _trigrams(c["text"])
        if not c_grams:
            continue
        overlap = len(seg_grams & c_grams) / len(c_grams)
        if overlap >= 0.08:
            scored.append((overlap, c))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:max_match]]


@bilibili_agent.tool_plain
async def get_danmakus(
    bvid: str, limit: int = 100, from_min: float = 0, to_min: float = 6,
) -> str:
    """获取视频弹幕。传入 bvid，返回弹幕列表（含时间戳和文本）。
    limit 限制条数，from_min/to_min 为时间范围（分钟）。"""
    if limit <= 0 or limit > 500:
        limit = 100
    try:
        v = video.Video(bvid=bvid)
        from_seg = max(0, int(from_min // 6))
        to_seg = max(from_seg, int((to_min - 1) // 6))
        danmakus = await v.get_danmakus(
            page_index=0, from_seg=from_seg, to_seg=to_seg,
        )
        lines: list[str] = []
        for i, dm in enumerate(danmakus[:limit], 1):
            ts = int(dm.dm_time)
            m, s = ts // 60, ts % 60
            text = dm.text.strip().replace("\n", " ")
            lines.append(
                f"{i}. [{m:02d}:{s:02d}] {text[:80]}"
                f"{'...' if len(text) > 80 else ''}"
            )
        total = len(danmakus)
        head = f"弹幕（{bvid}，前{min(limit, total)}条"
        if total > limit:
            head += f"，共{total}条"
        return head + "）:\n" + "\n".join(lines) if lines else "暂无弹幕。"
    except Exception as e:
        return f"获取失败: {e}"


@bilibili_agent.tool_plain
async def analyze_danmaku_density(
    bvid: str, window_sec: int = 60, step_sec: int = 15,
) -> str:
    """使用滑动窗口算法分析视频弹幕密度与内容，自动发现剧情段落和精彩程度。
    窗口 window_sec 秒（默认 60），步进 step_sec 秒（默认 15），75% 重叠交叉分析。
    三阶段切分：密度低谷自然切 → 密度低点切超长段 → 密度均匀时按弹幕话题变化切。"""
    bucket_sec = 15
    min_seg_sec = 30
    overlap_sec = 15  # 边界重叠采样秒数
    if window_sec < 30:
        window_sec = 30
    if step_sec < bucket_sec:
        step_sec = bucket_sec
    try:
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        duration = info.get("duration") or info.get("pages", [{}])[0].get("duration", 0)
        if duration <= 0:
            duration = 1500
        # 自适应段落上限：短片宽松，长片切细
        if duration <= 300:
            max_seg_sec = 90
        elif duration <= 900:
            max_seg_sec = 75
        else:
            max_seg_sec = 60
        to_seg = max(0, int(duration / 360))
        danmakus = await v.get_danmakus(
            page_index=0, from_seg=0, to_seg=to_seg,
        )
        if not danmakus:
            return "暂无弹幕，无法分析。"

        # 1. 分桶 + 补全空桶
        buckets: dict[int, list[str]] = defaultdict(list)
        for dm in danmakus:
            b = int(dm.dm_time) // bucket_sec * bucket_sec
            text = dm.text.strip().replace("\n", " ")[:100]
            if text:
                buckets[b].append(text)
        for t in range(0, duration + 1, bucket_sec):
            if t not in buckets:
                buckets[t] = []
        sorted_ts = sorted(buckets.keys())

        # 2. 滑动窗口密度曲线
        positions, densities = sliding_density(
            buckets, bucket_sec, duration, window_sec, step_sec,
        )
        # 3. 平滑
        smoothed = smooth(densities, window=3)

        # 4. 选取分界点（密度低谷 → 密度低点 → 内容话题变化）
        boundaries = select_boundaries(
            smoothed, positions, duration, step_sec,
            max_seg_sec, min_seg_sec, buckets, bucket_sec,
        )

        # 5. 切分 → 段落（含边界重叠采样）
        cut_times = sorted({0} | {positions[i] for i in boundaries} | {duration})
        segments: list[dict] = []
        for i in range(len(cut_times) - 1):
            seg_start, seg_end = cut_times[i], cut_times[i + 1]
            seg_ts = [t for t in sorted_ts if seg_start <= t < seg_end]
            if not seg_ts:
                continue
            total = sum(len(buckets[t]) for t in seg_ts)
            peak = max(len(buckets[t]) for t in seg_ts)
            # 边界重叠：采样前后各 overlap_sec 的弹幕作为过渡上下文
            pre_ts = [t for t in sorted_ts if seg_start - overlap_sec <= t < seg_start]
            post_ts = [t for t in sorted_ts if seg_end <= t < seg_end + overlap_sec]
            pre_ctx = segment_samples(buckets, pre_ts, count=2)
            post_ctx = segment_samples(buckets, post_ts, count=2)
            segments.append({
                "start": seg_start,
                "end": seg_end,
                "total": total,
                "peak": peak,
                "samples": segment_samples(buckets, seg_ts, count=8),
                "pre_ctx": pre_ctx,
                "post_ctx": post_ctx,
            })
        if not segments:
            return "弹幕过少，无法分段。"

        # 6. 获取高赞评论
        comments = await _fetch_top_comments(bvid, top_n=15)

        # 7. 为每个段落匹配相关评论
        for seg in segments:
            seg_ts = [t for t in sorted_ts if seg["start"] <= t < seg["end"]]
            all_text = " ".join(
                text for t in seg_ts for text in buckets.get(t, [])
            )
            seg["comments"] = _match_comments_to_segment(comments, all_text)

        # 8. 输出
        avg_peak = sum(s["peak"] for s in segments) / len(segments)
        lines: list[str] = [
            f"【剧情段落分析】{bvid}（时长 {fmt_ts(duration)}，"
            f"弹幕 {len(danmakus)} 条，高赞评论 {len(comments)} 条，"
            f"共 {len(segments)} 段）"
        ]
        for i, seg in enumerate(segments, 1):
            heat = heat_label(seg["peak"], avg_peak)
            desc = " | ".join(seg["samples"][:5])
            lines.append(
                f"  段落{i} {fmt_ts(seg['start'])}-{fmt_ts(seg['end'])}"
                f"（{seg['end'] - seg['start']}秒）"
                f" 弹幕{seg['total']}条 {heat}"
            )
            if seg.get("pre_ctx"):
                lines.append(f"    ↑前段尾声: {' | '.join(seg['pre_ctx'])}")
            if desc:
                lines.append(f"    弹幕摘要: {desc}")
            if seg.get("post_ctx"):
                lines.append(f"    ↓后段开头: {' | '.join(seg['post_ctx'])}")
            for c in seg.get("comments", []):
                lines.append(f"    相关评论[赞{c['like']}]: {c['text'][:100]}")

        # 附：未匹配到段落的高赞评论（整体剧情参考）
        matched_texts = {
            c["text"] for seg in segments for c in seg.get("comments", [])
        }
        unmatched = [c for c in comments if c["text"] not in matched_texts]
        if unmatched:
            lines.append("【高赞评论参考（整体剧情）】")
            for c in unmatched[:8]:
                lines.append(f"  [赞{c['like']}] {c['text'][:120]}")

        return "\n".join(lines)
    except Exception as e:
        return f"分析失败: {e}"
