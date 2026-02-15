import asyncio

from pydantic_ai.messages import ModelMessage

from panda_brain.deps import create_deps
from panda_brain.orchestrator import orchestrator


async def main():
    print("🐼 Panda Brain 已启动")
    print("输入 'quit' 或 'exit' 退出\n")

    deps = create_deps()
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
            result = await orchestrator.run(
                user_input,
                message_history=message_history,
                deps=deps,
            )
            print(f"\nPanda: {result.output}\n")
            message_history = result.all_messages()
        except Exception as e:
            print(f"\n错误: {e}\n")


def cli():
    asyncio.run(main())


if __name__ == "__main__":
    cli()
