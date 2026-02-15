"""记录已抓取的 bvid，避免重复抓取。"""

import json
from pathlib import Path

from panda_brain.config import settings

_REGISTRY: dict[str, list[str]] | None = None


def _path() -> Path:
    p = Path(settings.bilibili_fetched_registry_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _load() -> dict[str, list[str]]:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    p = _path()
    if not p.exists():
        _REGISTRY = {"danmaku": [], "comments": []}
        return _REGISTRY
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        _REGISTRY = {
            "danmaku": list(data.get("danmaku") or []),
            "comments": list(data.get("comments") or []),
        }
        return _REGISTRY
    except Exception:
        _REGISTRY = {"danmaku": [], "comments": []}
        return _REGISTRY


def _save() -> None:
    global _REGISTRY
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = _REGISTRY if _REGISTRY is not None else {"danmaku": [], "comments": []}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_fetched(bvid: str, kind: str = "danmaku") -> bool:
    """是否已抓取过该 bvid 的 kind（danmaku / comments）。"""
    reg = _load()
    return bvid in reg.get(kind, [])


def mark_fetched(bvid: str, kind: str = "danmaku") -> None:
    """标记该 bvid 的 kind 已抓取。"""
    global _REGISTRY
    reg = _load()
    lst = reg.setdefault(kind, [])
    if bvid not in lst:
        lst.append(bvid)
        _save()
