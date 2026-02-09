from pydantic_ai import Agent

from panda_brain.config import get_model

network_agent = Agent(
    get_model(),
    system_prompt=(
        "你是一个网络诊断专家。你可以查询本机的网络信息。\n"
        "使用提供的工具获取 IP 地址等网络信息，然后将结果清晰地呈现给用户。\n"
        "始终用中文回答。"
    ),
)
