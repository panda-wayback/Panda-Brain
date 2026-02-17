"""点播智能体：理解「播什么、从哪时刻播、快进/倒退」，调 bilibili 解析拿链接并执行播放，记录点播与对话。"""

from pathlib import Path

from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps
from panda_brain.utils.prompt_loader import load_system_prompt

_YAML_PATH = Path(__file__).resolve().parent / "system_prompt.yaml"
_DEFAULT_PROMPT = (
    "你是点播智能体：根据用户意图获取 B 站番剧播放链接并执行播放，支持多轮上下文。\n\n"
    "1. 用户要播某集（如「骨王第三集」「从5分30秒播」）：先 get_bangumi_play_url(keyword, season, episode) 拿到播放链接，再 play(url, start_time_sec) 在浏览器打开；未说第几季则 season=1。多轮中若用户只说「第四集」则沿用上一轮番剧名。\n\n"
    "2. 用户说快进/倒退（如「快进30秒」「倒退1分钟」）：调用 seek_relative(delta_sec)，正数为快进、负数为倒退；通过 Playwright 控制当前播放页执行并写入记录。\n\n"
    "3. 每次执行播放后调用 record_playback 写入点播记录，便于后续根据习惯优化。\n\n"
    "始终用中文回答。"
)

playback_agent = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=load_system_prompt(_YAML_PATH, default=_DEFAULT_PROMPT),
)
