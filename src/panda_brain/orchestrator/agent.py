from pydantic_ai import Agent

from panda_brain.config import get_model

orchestrator = Agent(
    get_model(),
    system_prompt=(
        "你是 Panda Brain，一个智能编排器。\n"
        "根据用户意图选择合适的工具委托给专家处理，简单问题直接回答。\n"
        "始终用中文回答。"
    ),
)
