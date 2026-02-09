from pydantic_ai import RunContext

from panda_brain.agents.coder import coder_agent
from panda_brain.agents.network import network_agent
from panda_brain.orchestrator.agent import orchestrator


@orchestrator.tool
async def delegate_to_coder(ctx: RunContext, task: str) -> str:
    """将编程、代码生成、代码分析、Shell 命令等技术任务委托给代码专家 Agent。"""
    result = await coder_agent.run(task, usage=ctx.usage)
    return result.output


@orchestrator.tool
async def delegate_to_network(ctx: RunContext, task: str) -> str:
    """将网络信息查询任务（如查看 IP 地址）委托给网络诊断专家 Agent。"""
    result = await network_agent.run(task, usage=ctx.usage)
    return result.output
