"""
一次输出完整弹幕分析结果（直接调用工具，不经 LLM）。

用法:
    PYTHONPATH=src python -m panda_brain.agents.bilibili.test_danmaku_full [bvid]
    默认 bvid: BV1Ks411S7co
"""
import asyncio
import sys

from panda_brain.agents.bilibili.tools.danmaku.tools import analyze_danmaku_density


async def main(bvid: str, max_minutes: float | None = None) -> None:
    print(f"分析 {bvid}，输出完整结果…\n")
    max_sec = int(max_minutes * 60) if max_minutes else None
    full = await analyze_danmaku_density(bvid, max_duration_sec=max_sec)
    print(full)


if __name__ == "__main__":
    # python -m ... [bvid] [max_minutes]，不传 max_minutes 则分析全片
    bvid = sys.argv[1] if len(sys.argv) > 1 else "BV1Ks411S7co"
    max_min = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0  # 默认只测前 3 分钟
    asyncio.run(main(bvid, max_minutes=max_min))
