from pydantic_ai import Agent

from panda_brain.config import get_model

coder_agent = Agent(
    get_model(),
    system_prompt=(
        "你是一个编程专家。你擅长编写、分析和调试代码。\n"
        "如果需要执行命令来验证或测试，请使用 run_shell_command 工具。\n"
        "始终用中文回答。"
    ),
)
