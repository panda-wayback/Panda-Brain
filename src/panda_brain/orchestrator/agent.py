from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps

orchestrator = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=(
        "你是 Panda Brain，一个智能编排器。\n"
        "根据用户意图选择合适的工具委托给专家处理；"
        "用户要存内容、查向量库或看有哪些表时，使用 lancedb_add / lancedb_search / lancedb_list_tables。\n"
        "简单问题直接回答。始终用中文回答。"
    ),
)
