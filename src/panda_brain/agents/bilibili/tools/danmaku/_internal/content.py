"""基于弹幕内容的话题变化检测。"""


def text_bigrams(texts: list[str]) -> set[str]:
    """提取文本列表的字符 bigram 集合。"""
    grams: set[str] = set()
    for t in texts:
        for i in range(len(t) - 1):
            grams.add(t[i: i + 2])
    return grams


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard 相似度，0~1，越小说明话题差异越大。"""
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 1.0


def content_split_point(
    buckets: dict[int, list[str]],
    bucket_sec: int,
    seg_start: int,
    seg_end: int,
    min_margin: int,
    analysis_window: int = 30,
) -> tuple[int | None, float]:
    """在密度均匀的段落中，用弹幕内容的 Jaccard 距离找话题转变最大的切分点。

    对段落按 analysis_window 分小窗，比较相邻窗口的 bigram 集合。
    返回 (最佳切分时间戳, 最大话题变化量)。
    """
    windows: list[tuple[int, set[str]]] = []
    for start in range(seg_start, seg_end, analysis_window):
        end = min(start + analysis_window, seg_end)
        texts: list[str] = []
        for t in range(start, end, bucket_sec):
            texts.extend(buckets.get(t, []))
        grams = text_bigrams(texts)
        windows.append((start, grams))

    if len(windows) < 3:
        return None, 0.0

    best_pos: int | None = None
    max_change = 0.0
    for i in range(1, len(windows)):
        pos = windows[i][0]
        if pos <= seg_start + min_margin or pos >= seg_end - min_margin:
            continue
        change = 1.0 - jaccard(windows[i - 1][1], windows[i][1])
        if change > max_change:
            max_change = change
            best_pos = pos

    return best_pos, max_change
