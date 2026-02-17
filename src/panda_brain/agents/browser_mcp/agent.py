"""浏览器 MCP 智能体：接入 Playwright MCP，使用 browser_navigate/click/snapshot/evaluate 等工具自动化浏览器。"""

from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from panda_brain.config import get_model
from panda_brain.deps import Deps
from panda_brain.utils.prompt_loader import load_system_prompt

_YAML_PATH = Path(__file__).resolve().parent / "system_prompt.yaml"
_DEFAULT_PROMPT = (
    "你是 B 站番剧播放助手。通过 get_play_url_from_fetcher 向 bilibili_fetcher 拿链接，取返回第一行用 browser_navigate 打开；"
    "「第N分钟」用 browser_evaluate 设 video.currentTime。始终用中文回答。"
)

# 持久化 profile 目录（保留登录态），与 playback 分开避免同时占用冲突
_USER_DATA_DIR = str((Path.home() / ".config" / "panda_brain_browser_mcp").resolve())

# Playwright MCP 通过 stdio 子进程接入（需 Node.js 与 npx）
playwright_mcp_server = MCPServerStdio(
    "npx",
    args=[
        "@playwright/mcp@latest",
        "--user-data-dir",
        _USER_DATA_DIR,
    ],
    timeout=60,
)

browser_mcp_agent = Agent(
    get_model(),
    deps_type=Deps,
    toolsets=[playwright_mcp_server],
    system_prompt=load_system_prompt(_YAML_PATH, default=_DEFAULT_PROMPT),
)
