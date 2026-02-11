"""弹幕分析共享工具函数。"""


def fmt_ts(sec: int) -> str:
    """秒数格式化为 MM:SS。"""
    return f"{sec // 60:02d}:{sec % 60:02d}"


def heat_label(peak: float, avg_peak: float) -> str:
    """根据峰值与均值比标注精彩度。"""
    if avg_peak <= 0:
        return ""
    ratio = peak / avg_peak
    if ratio >= 2.0:
        return "★★★ 超高能"
    if ratio >= 1.3:
        return "★★ 高能"
    if ratio >= 0.7:
        return "★ 普通"
    return "- 平淡"


def segment_samples(
    buckets: dict[int, list[str]], ts_list: list[int], count: int = 5
) -> list[str]:
    """从段落中均匀采样弹幕，覆盖首/中/尾，去重。"""
    if not ts_list:
        return []
    step = max(1, len(ts_list) // count)
    pick_indices = list(range(0, len(ts_list), step))[:count]
    samples: list[str] = []
    seen: set[str] = set()
    for idx in pick_indices:
        for text in buckets.get(ts_list[idx], [])[:3]:
            key = text[:30]
            if key not in seen:
                seen.add(key)
                samples.append(text[:80])
                break
        if len(samples) >= count:
            break
    return samples
