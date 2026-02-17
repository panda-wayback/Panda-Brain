"""从 YAML 规则配置拼装 agent system prompt。"""

from pathlib import Path

import yaml


def load_system_prompt(path: str | Path, default: str | None = None) -> str:
    """加载 YAML 规则并拼装为 system prompt。
    
    结构：role + 编号规则列表(when/action/example) + footer。
    若文件不存在且 default 不为 None 则返回 default。
    """
    path = Path(path)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"system_prompt.yaml not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    role = (raw.get("role") or "").strip()
    footer = (raw.get("footer") or "").strip()
    rules: list[dict] = raw.get("rules") or []
    parts = [role]
    for i, r in enumerate(rules, 1):
        when = (r.get("when") or "").strip().rstrip("。")
        action = (r.get("action") or "").strip().rstrip("。")
        example = (r.get("example") or "").strip()
        line = f"{i}. {when}：{action}"
        if example:
            line += f"。示例：{example}。"
        else:
            line += "。"
        parts.append(line)
    if footer:
        parts.append(footer)
    return "\n\n".join(parts)
