"""
单独测试 B 站智能体。直接与 bilibili_agent 对话，不经 orchestrator。

用法:
    python -m panda_brain.agents.bilibili.test_agent
    或 PYTHONPATH=src python src/panda_brain/agents/bilibili/test_agent.py
"""
import asyncio

from pydantic_ai.messages import ModelMessage

from panda_brain.agents.bilibili import bilibili_agent


async def main():
    print("🎬 B 站智能体已启动（单独测试模式）")
    print("输入 'quit' 或 'exit' 退出\n")

    message_history: list[ModelMessage] = []

    while True:
        try:
            user_input = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("再见!")
            break

        try:
            result = await bilibili_agent.run(user_input, message_history=message_history)
            print(f"\nB站: {result.output}\n")
            message_history = result.all_messages()
        except Exception as e:
            print(f"\n错误: {e}\n")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
