import asyncio

from panda_brain.agents.coder.agent import coder_agent


@coder_agent.tool_plain
async def run_shell_command(command: str) -> str:
    """在本地 shell 中执行命令并返回结果。用于运行代码、查看文件、安装依赖等。"""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = stdout.decode() if stdout else ""
        errors = stderr.decode() if stderr else ""
        return f"exit_code: {proc.returncode}\nstdout:\n{output}\nstderr:\n{errors}"
    except asyncio.TimeoutError:
        return "命令执行超时 (30秒)"
    except Exception as e:
        return f"执行错误: {e}"
