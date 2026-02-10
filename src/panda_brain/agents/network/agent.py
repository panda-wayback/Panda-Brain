from pydantic_ai import Agent

from panda_brain.config import get_model

network_agent = Agent(
    get_model(),
    system_prompt=(
        "你是一个网络诊断专家。\n"
        "当用户询问网络状况时，主动调用所有工具进行全面检测，不要反问用户。\n"
        "结果按以下顺序呈现：网速和延迟 → IP 地址信息。\n"
        "始终用中文回答。"
    ),
)
