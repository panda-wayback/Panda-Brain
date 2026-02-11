"""滑动窗口密度曲线计算 & 局部最小值检测。"""


def smooth(values: list[float], window: int = 3) -> list[float]:
    """滑动平均平滑。"""
    n = len(values)
    if n == 0:
        return []
    half = window // 2
    return [
        sum(values[max(0, i - half): min(n, i + half + 1)])
        / (min(n, i + half + 1) - max(0, i - half))
        for i in range(n)
    ]


def sliding_density(
    buckets: dict[int, list[str]],
    bucket_sec: int,
    duration: int,
    window_sec: int,
    step_sec: int,
) -> tuple[list[int], list[float]]:
    """滑动窗口计算密度曲线，重叠部分交叉观察。"""
    positions: list[int] = []
    densities: list[float] = []
    for start in range(0, duration, step_sec):
        end = min(start + window_sec, duration + bucket_sec)
        count = sum(len(buckets.get(t, [])) for t in range(start, end, bucket_sec))
        positions.append(start)
        densities.append(float(count))
    return positions, densities


def collect_minima(smoothed: list[float]) -> list[tuple[int, float]]:
    """找所有局部最小值及其相对深度，按深度降序排列。"""
    n = len(smoothed)
    if n <= 2:
        return []
    minima: list[tuple[int, float]] = []
    for i in range(1, n - 1):
        if smoothed[i] > smoothed[i - 1] or smoothed[i] > smoothed[i + 1]:
            continue
        left_peak = max(smoothed[max(0, i - 5): i])
        right_peak = max(smoothed[i + 1: min(n, i + 6)])
        peak = max(left_peak, right_peak, 1e-9)
        depth = 1.0 - smoothed[i] / peak
        minima.append((i, depth))
    minima.sort(key=lambda x: -x[1])
    return minima
