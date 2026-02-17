"""LanceDB 行级约定：search 返回的每行含 text、source、extra 等。extra 常存为 JSON 字符串。"""

import json


def parse_extra(row: dict) -> dict:
    """从 search 返回的行中解析 extra 为 dict。extra 可能已是 dict 或 JSON 字符串，解析失败返回 {}。"""
    e = row.get("extra")
    if isinstance(e, dict):
        return e
    if isinstance(e, str):
        try:
            return json.loads(e) or {}
        except json.JSONDecodeError:
            pass
    return {}
