from pathlib import Path

import yaml
from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps

_PROMPT_DIR = Path(__file__).resolve().parent
_YAML_PATH = _PROMPT_DIR / "system_prompt.yaml"


def _load_system_prompt() -> str:
    """从 YAML 规则配置拼装系统提示。结构：role + 编号规则列表 + footer。"""
    raw = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
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


bilibili_fetcher_agent = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=_load_system_prompt(),
)
