from pathlib import Path

from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps
from panda_brain.utils.prompt_loader import load_system_prompt

_YAML_PATH = Path(__file__).resolve().parent / "system_prompt.yaml"

bilibili_fetcher_agent = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=load_system_prompt(_YAML_PATH),
)
