"""三阶段分界点选取：密度低谷 → 密度低点 → 内容话题变化。"""

from panda_brain.agents.bilibili.tools.danmaku._internal.content import content_split_point
from panda_brain.agents.bilibili.tools.danmaku._internal.density import collect_minima


def select_boundaries(
    smoothed: list[float],
    positions: list[int],
    duration: int,
    step_sec: int,
    max_seg_sec: int,
    min_seg_sec: int,
    buckets: dict[int, list[str]],
    bucket_sec: int,
    natural_depth: float = 0.2,
) -> list[int]:
    """三阶段选取分界点：

    1) 贪心选取深度 >= natural_depth 的密度自然低谷
    2) 对超长段在其内部密度低点处切分
    3) 密度均匀无低点时，用弹幕内容话题变化切分
    """
    minima = collect_minima(smoothed)
    min_gap = max(2, min_seg_sec // step_sec)
    selected: list[int] = []

    # ── 阶段 1：自然密度低谷 ──
    for idx, depth in minima:
        if depth < natural_depth:
            break
        if all(abs(idx - s) >= min_gap for s in selected):
            selected.append(idx)

    # ── 阶段 2+3：处理超长段 ──
    max_iter = max(20, duration // max_seg_sec * 2)
    for _ in range(max_iter):
        selected_sorted = sorted(selected)
        cuts = [0] + [positions[i] for i in selected_sorted] + [duration]
        long_seg = None
        for j in range(len(cuts) - 1):
            if cuts[j + 1] - cuts[j] > max_seg_sec:
                long_seg = (cuts[j], cuts[j + 1])
                break
        if long_seg is None:
            break
        s, e = long_seg
        # margin 自适应：不超过段落长度的 1/3，确保搜索区间够大
        margin = min(min_seg_sec, (e - s) // 3)

        # 阶段 2：尝试密度低点
        best = None
        for idx, _ in minima:
            if idx in selected:
                continue
            pos = positions[idx]
            if pos <= s + margin or pos >= e - margin:
                continue
            if all(abs(idx - si) >= min_gap for si in selected):
                best = idx
                break
        if best is not None:
            selected.append(best)
            continue

        # 阶段 3：密度均匀 → 用弹幕内容话题变化切分
        split_pos, change = content_split_point(
            buckets, bucket_sec, s, e, margin,
        )
        if split_pos is not None and change > 0.05:
            closest = min(
                range(len(positions)),
                key=lambda i: abs(positions[i] - split_pos),
            )
            if closest not in selected and \
               positions[closest] > s + margin and \
               positions[closest] < e - margin:
                selected.append(closest)
                continue

        # 兜底：中点切分
        mid = (s + e) // 2 // step_sec * step_sec
        closest = min(range(len(positions)), key=lambda i: abs(positions[i] - mid))
        if closest not in selected and \
           positions[closest] > s + margin and \
           positions[closest] < e - margin:
            selected.append(closest)
        else:
            break

    return sorted(selected)
