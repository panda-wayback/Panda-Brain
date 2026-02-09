from pydantic_ai import Agent

from panda_brain.config import get_model

orchestrator = Agent(
    get_model(),
    system_prompt=(
        "你是 Panda Brain，一个智能多 Agent 编排器。\n"
        "你的职责是理解用户的意图，并决定如何最好地完成任务：\n"
        "- 对于编程、代码、技术命令相关的任务，使用 delegate_to_coder 工具\n"
        "- 对于网络信息（IP 地址查询等），使用 delegate_to_network 工具\n"
        "- 对于一般性问题（聊天、知识问答等），直接回答即可\n"
        "始终用中文回答。"
    ),
)
