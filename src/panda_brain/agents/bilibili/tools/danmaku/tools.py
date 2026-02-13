"""弹幕相关 tool_plain 注册入口。"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx
from bilibili_api import Credential, video
from bilibili_api import comment as comment_api
from bilibili_api.comment import CommentResourceType, OrderType
from bilibili_api.utils.aid_bvid_transformer import bvid2aid

from panda_brain.agents.bilibili.agent import bilibili_agent
from panda_brain.config import settings

# 窗口内：每批最多送 LLM 的条数，避免一次输入过多导致截断
_BATCH_SIZE = 15
# 去重后若仍超过此数，则分批概括再合并
_MERGE_THRESHOLD = 25
# 单次 prompt 最多展示的弹幕条数（去重后带计数）
_MAX_ITEMS_IN_PROMPT = 50


def _fmt_ts(sec: int) -> str:
    """秒数 → MM:SS。"""
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _normalize_danmaku(text: str) -> str:
    """语法归一：去空白、重复字符合并，便于去重。"""
    t = text.strip().replace("\n", " ").replace("\t", " ")
    t = re.sub(r"\s+", " ", t).strip()
    # 同一字符连续出现 2+ 次合并为 1 次（如 哈哈哈哈→哈哈，避免过长）
    t = re.sub(r"(.)\1+", r"\1\1", t)
    return t[:100]


def _trigrams(s: str) -> set[str]:
    """字符 trigram 集合，用于简单语义相似。"""
    return {s[i : i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else set()


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _dedupe_window(texts: list[str]) -> list[tuple[str, int]]:
    """语法去重：同文合并为 (文本, 出现次数)，按次数降序。"""
    normalized = [_normalize_danmaku(t) for t in texts if _normalize_danmaku(t)]
    cnt = Counter(normalized)
    return sorted(cnt.items(), key=lambda x: -x[1])


def _merge_similar(items: list[tuple[str, int]], thresh: float = 0.82) -> list[tuple[str, int]]:
    """简单语义去重：trigram Jaccard 超过 thresh 的合并为一条，保留最长文本、次数相加。"""
    if len(items) <= 1:
        return items
    out: list[tuple[str, int]] = []
    used = [False] * len(items)
    for i, (text, count) in enumerate(items):
        if used[i]:
            continue
        tri = _trigrams(text)
        merged_text, merged_count = text, count
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            text2, count2 = items[j]
            if _jaccard(tri, _trigrams(text2)) >= thresh:
                used[j] = True
                merged_count += count2
                if len(text2) > len(merged_text):
                    merged_text = text2
        out.append((merged_text, merged_count))
    return sorted(out, key=lambda x: -x[1])


async def _llm_one_line(prompt: str, timeout: int = 25) -> str:
    """单次 LLM 调用，返回一行概括，避免长输出中断。"""
    ollama_host = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": settings.default_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            r.raise_for_status()
            text = (r.json().get("response") or "").strip()
            return text[:200] if text else ""
    except Exception:
        return ""


async def _fetch_top_comments(bvid: str, top_n: int = 10) -> list[dict]:
    """获取高赞评论，失败返回空列表。"""
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


def _format_danmaku_for_prompt(items: list[tuple[str, int]], max_items: int = _MAX_ITEMS_IN_PROMPT) -> str:
    """去重后的 (文本, 次数) 格式化为给 LLM 的短文本。"""
    lines = [f"{text} (x{cnt})" if cnt > 1 else text for text, cnt in items[:max_items]]
    return "\n".join(lines) if lines else "（无）"


async def _summarize_batch(danmaku_block: str) -> str:
    """对一批弹幕做一句话概括（输入不宜过长）。"""
    prompt = f"""下面是一批弹幕（可能带 x数量），用一句话概括这批在讨论什么。只输出一句话，不要前缀和序号。

弹幕：
{danmaku_block}

一句话概括："""
    return await _llm_one_line(prompt)


async def _merge_summaries(summaries: list[str], start_ts: str, end_ts: str) -> str:
    """把多句概括合并成一句（循环压缩）。"""
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    block = "\n".join(f"{i+1}. {s}" for i, s in enumerate(summaries))
    prompt = f"""下面是对同一时间段（{start_ts}-{end_ts}）弹幕的多条概括，请合并成一句话。只输出一句，不要前缀。

{block}

合并成一句话："""
    return await _llm_one_line(prompt)


async def _analyze_interval_via_llm(
    start_sec: int, end_sec: int,
    danmaku_texts: list[str], comments: list[dict],
) -> str:
    """循环压缩：先语法/语义去重，若仍很多则分批概括再合并，避免一次输入过多导致截断。"""
    start_ts = _fmt_ts(start_sec)
    end_ts = _fmt_ts(end_sec)

    # 1. 语法去重 → (文本, 次数)
    items = _dedupe_window(danmaku_texts)
    # 2. 简单语义去重：相似句合并
    items = _merge_similar(items)

    if not items:
        return ""

    # 3. 若条数不多，一次送 LLM（带评论）
    if len(items) <= _MERGE_THRESHOLD:
        danmaku_block = _format_danmaku_for_prompt(items)
        comment_block = "\n".join(f"[赞{c['like']}] {c['text'][:120]}" for c in comments[:10])
        prompt = f"""根据以下弹幕（{start_ts}-{end_ts}）和评论，用一句话概括这段在讲什么。只输出一句。

弹幕（去重后）：
{danmaku_block}

评论：
{comment_block}

一句话："""
        return await _llm_one_line(prompt)

    # 4. 条数多：分批概括，再合并（循环压缩）
    batch_summaries: list[str] = []
    for i in range(0, len(items), _BATCH_SIZE):
        batch = items[i : i + _BATCH_SIZE]
        block = _format_danmaku_for_prompt(batch, max_items=_BATCH_SIZE)
        s = await _summarize_batch(block)
        if s:
            batch_summaries.append(s)
    if not batch_summaries:
        return ""
    merged = await _merge_summaries(batch_summaries, start_ts, end_ts)
    return merged


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
    bvid: str,
    window_sec: int = 30,
    step_sec: int = 15,
    top_comments: int = 10,
    max_duration_sec: int | None = None,
) -> str:
    """使用滑动窗口，根据弹幕以及前 N 条高赞评论，分析每个时间区间在讲什么事情。
    30 秒区间、15 秒交叉步进，重叠窗口便于发现一大段剧情。
    window_sec：窗口长度（秒），默认 30。
    step_sec：步进（秒），默认 15（与窗口交叉 15 秒）。
    top_comments：参与分析的评论条数，默认 10（可改为 100）。
    max_duration_sec：只分析视频前 N 秒，不传则分析全片（长片会很多次 LLM 调用，耗时长）。"""
    if window_sec < 15:
        window_sec = 15
    if step_sec < 5:
        step_sec = 5
    if step_sec > window_sec:
        step_sec = window_sec
    top_comments = max(1, min(100, top_comments))

    try:
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        duration = info.get("duration") or info.get("pages", [{}])[0].get("duration", 0)
        if duration <= 0:
            duration = 1500

        analyze_duration = duration
        if max_duration_sec is not None and max_duration_sec > 0:
            analyze_duration = min(duration, max_duration_sec)

        to_seg = max(0, int(duration / 360))
        danmakus = await v.get_danmakus(
            page_index=0, from_seg=0, to_seg=to_seg,
        )
        if not danmakus:
            return "暂无弹幕，无法分析。"

        comments = await _fetch_top_comments(bvid, top_n=top_comments)

        # 区间数量（与下面 while 一致：start = 0, step_sec, 2*step_sec, ... 且 start < analyze_duration）
        num_windows = max(1, (analyze_duration + step_sec - 1) // step_sec)

        # 滑动窗口：每个窗口内的弹幕文本
        results: list[dict] = []
        start = 0
        idx = 0
        while start < analyze_duration:
            end = min(start + window_sec, duration)
            in_window = [
                dm.text.strip().replace("\n", " ")[:100]
                for dm in danmakus
                if start <= int(dm.dm_time) < end and dm.text.strip()
            ]
            idx += 1
            sys.stderr.write(f"\r正在分析 {idx}/{num_windows} {_fmt_ts(start)}-{_fmt_ts(end)}…")
            sys.stderr.flush()
            summary = await _analyze_interval_via_llm(
                start, end, in_window, comments
            )
            results.append({
                "start_sec": start,
                "end_sec": end,
                "start_ts": _fmt_ts(start),
                "end_ts": _fmt_ts(end),
                "danmaku_count": len(in_window),
                "summary": summary,
            })
            start += step_sec
        if num_windows > 0:
            sys.stderr.write("\r" + " " * 60 + "\r")
            sys.stderr.flush()

        # 输出
        limit_note = f"（仅前{analyze_duration}秒）" if analyze_duration < duration else ""
        lines = [
            f"【弹幕剧情分析】{bvid} 时长{_fmt_ts(duration)} "
            f"弹幕{len(danmakus)}条 评论{len(comments)}条 滑动窗口{window_sec}秒 步进{step_sec}秒{limit_note}",
            "",
        ]
        for r in results:
            line = f"{r['start_ts']}-{r['end_ts']}（{r['danmaku_count']}条弹幕）"
            if r["summary"]:
                line += " " + r["summary"]
            lines.append(line)

        # 写入 JSON
        out_dir = Path(os.environ.get("BILIBILI_ANALYSIS_OUTPUT_DIR", "output"))
        out_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"bilibili_danmaku_{bvid}_{ts_str}.json"
        export_payload = {
            "bvid": bvid,
            "duration_sec": duration,
            "window_sec": window_sec,
            "step_sec": step_sec,
            "danmaku_count": len(danmakus),
            "top_comments": top_comments,
            "intervals": results,
        }
        out_path.write_text(
            json.dumps(export_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return (
            f"完整数据已写入 {out_path}\n\n" + "\n".join(lines)
        )
    except Exception as e:
        return f"分析失败: {e}"
