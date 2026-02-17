"""弹幕抓取并写入 LanceDB。

- 拉取：get_danmakus(from_seg=0, to_seg=None)，库内按 segment 拉整集。
- 存储：按秒聚合，每秒一行。每行含该秒弹幕数量(danmaku_count)、该秒弹幕的语义聚合文本；
  可选用 LLM 对该秒弹幕做一句话概括，减少冗余。LLM 概括时使用并发+信号量限流，避免串行阻塞。
"""

import asyncio
import json
from collections import defaultdict

import httpx
from bilibili_api import video
from bilibili_api.exceptions import DanmakuClosedException

from panda_brain.agents.bilibili_fetcher.tools._common import (
    TABLE_DANMAKU,
    DANMAKU_TEXT_MAX,
    DANMAKU_MERGE_PER_SEC_MAX,
)
from panda_brain.config import settings
from panda_brain.deps import Deps

# 弹幕 LLM 概括时的最大并发数，避免压垮本地 Ollama
MAX_CONCURRENT_DANMAKU_LLM = 5


def _extra_per_sec(time_sec: int, danmaku_count: int) -> str:
    """按秒存储的 extra：来源站点 + time_sec + 该秒弹幕数量。"""
    return json.dumps(
        {"source_site": "bilibili", "time_sec": time_sec, "danmaku_count": danmaku_count},
        ensure_ascii=False,
    )


async def _summarize_second_with_llm(merged_text: str, timeout: int = 15) -> str:
    """用 Ollama 对该秒的弹幕合并文本做一句话概括（语义聚合）。"""
    if not merged_text.strip():
        return ""
    prompt = f"""下面是一秒内的多条弹幕内容，用一句话概括这一秒观众在讨论/反应什么。只输出这一句话，不要序号和前缀。

弹幕：
{merged_text[:600]}

一句话概括："""
    try:
        host = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{host}/api/generate",
                json={"model": settings.default_model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            text = (r.json().get("response") or "").strip()
            return text[:300] if text else merged_text[:DANMAKU_MERGE_PER_SEC_MAX]
    except Exception:
        return merged_text[:DANMAKU_MERGE_PER_SEC_MAX]


async def fetch_danmaku_and_store(
    deps: Deps,
    bvid: str,
    limit: int = 0,
    summarize_with_llm: bool = False,
) -> tuple[int, str]:
    """抓取 bvid 整集弹幕，按秒聚合后写入 LanceDB，并标记已抓取。

    - 存储：每秒一行；text 为该秒弹幕合并文本（或 LLM 一句话概括），extra 含 time_sec、danmaku_count。
    - limit：参与聚合的弹幕总条数上限，0 表示不截断。
    - summarize_with_llm：是否用 Ollama 对该秒弹幕做一句话概括（语义聚合）；启用时并发调用并限流，避免串行阻塞。"""
    if deps.lancedb.table_has_source(TABLE_DANMAKU, bvid):
        return 0, "已存在，跳过"
    try:
        v = video.Video(bvid=bvid)
        danmakus = await v.get_danmakus(page_index=0, from_seg=0, to_seg=None)
        if not danmakus:
            return 0, "无弹幕"

        # 按秒分组： time_sec -> [弹幕文本, ...]
        to_take = danmakus if limit <= 0 else danmakus[:limit]
        by_sec: dict[int, list[str]] = defaultdict(list)
        for dm in to_take:
            text = (dm.text or "").strip().replace("\n", " ")[:DANMAKU_TEXT_MAX]
            if not text:
                continue
            by_sec[int(dm.dm_time)].append(text)

        if not by_sec:
            return 0, "无有效弹幕"

        sorted_secs = sorted(by_sec.keys())
        if summarize_with_llm:
            sem = asyncio.Semaphore(MAX_CONCURRENT_DANMAKU_LLM)

            async def summarize_one(time_sec: int) -> tuple[int, str]:
                texts = by_sec[time_sec]
                count = len(texts)
                merged = " ".join(texts)[:DANMAKU_MERGE_PER_SEC_MAX]
                if merged:
                    async with sem:
                        merged = await _summarize_second_with_llm(merged)
                if not merged:
                    merged = f"（{count} 条弹幕）"
                return time_sec, merged, count

            results = await asyncio.gather(
                *[summarize_one(sec) for sec in sorted_secs],
                return_exceptions=False,
            )
            items = [
                {
                    "text": merged,
                    "source": bvid,
                    "extra": _extra_per_sec(time_sec, count),
                }
                for time_sec, merged, count in results
            ]
        else:
            items = []
            for time_sec in sorted_secs:
                texts = by_sec[time_sec]
                count = len(texts)
                merged = " ".join(texts)[:DANMAKU_MERGE_PER_SEC_MAX]
                if not merged:
                    merged = f"（{count} 条弹幕）"
                items.append({
                    "text": merged,
                    "source": bvid,
                    "extra": _extra_per_sec(time_sec, count),
                })

        n = deps.lancedb.add_documents(TABLE_DANMAKU, items)
        return n, f"已按秒聚合写入 {n} 条（共 {sum(len(by_sec[s]) for s in by_sec)} 条原始弹幕）"
    except DanmakuClosedException:
        return 0, "该视频弹幕已关闭"
    except Exception as e:
        return 0, f"抓取失败: {e}"
