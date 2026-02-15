from pydantic_ai import RunContext

from panda_brain.agents.bilibili import bilibili_agent
from panda_brain.agents.coder import coder_agent
from panda_brain.agents.network import network_agent
from panda_brain.deps import Deps
from panda_brain.orchestrator.agent import orchestrator


@orchestrator.tool
async def lancedb_add(
    ctx: RunContext[Deps],
    table_name: str,
    text: str,
    source: str | None = None,
    extra: str | None = None,
) -> str:
    """将一条文本写入 LanceDB 指定表。表不存在时会自动创建。可选 source（来源）、extra（额外元数据）。"""
    try:
        item: dict = {"text": text}
        if source is not None:
            item["source"] = source
        if extra is not None:
            item["extra"] = extra
        n = ctx.deps.lancedb.add_documents(table_name, [item])
        return f"已向表「{table_name}」写入 {n} 条记录。"
    except Exception as e:
        return f"写入失败: {e}"


@orchestrator.tool
async def lancedb_search(
    ctx: RunContext[Deps],
    table_name: str,
    query: str,
    limit: int = 10,
) -> str:
    """在 LanceDB 指定表中做语义检索：根据 query 查找最相关的记录，返回最多 limit 条（默认 10）。"""
    try:
        rows = ctx.deps.lancedb.search(table_name, query, limit=limit)
        if not rows:
            return f"表「{table_name}」中未找到与「{query}」相关的结果。"
        lines = []
        for i, r in enumerate(rows, 1):
            text = r.get("text", "")
            src = r.get("source") or ""
            ext = r.get("extra") or ""
            dist = r.get("_distance", "")
            parts = [f"{i}. {text}"]
            if src:
                parts.append(f" [来源: {src}]")
            if ext:
                parts.append(f" [extra: {ext}]")
            if dist != "":
                parts.append(f" (距离: {dist})")
            lines.append("".join(parts))
        return "\n".join(lines)
    except Exception as e:
        return f"检索失败: {e}"


@orchestrator.tool
async def lancedb_list_tables(ctx: RunContext[Deps]) -> str:
    """列出当前 LanceDB 中所有表名。"""
    try:
        names = ctx.deps.lancedb.list_tables()
        if not names:
            return "当前没有任何表。"
        return "当前表: " + ", ".join(names)
    except Exception as e:
        return f"列表失败: {e}"


@orchestrator.tool
async def delegate_to_coder(ctx: RunContext[Deps], task: str) -> str:
    """将编程、代码生成、代码分析、Shell 命令等技术任务委托给代码专家 Agent。"""
    result = await coder_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    return result.output


@orchestrator.tool
async def delegate_to_network(ctx: RunContext[Deps], task: str) -> str:
    """将网络信息查询任务（如查看 IP 地址）委托给网络诊断专家 Agent。"""
    result = await network_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    return result.output


@orchestrator.tool
async def delegate_to_bilibili(ctx: RunContext[Deps], task: str) -> str:
    """将 B 站相关任务（番剧查询、播放链接获取等）委托给 B 站专家 Agent。"""
    result = await bilibili_agent.run(task, deps=ctx.deps, usage=ctx.usage)
    return result.output
