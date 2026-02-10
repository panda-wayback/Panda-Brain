---
name: panda-brain-dev
description: Panda Brain 多智能体项目的架构规范和开发指南。在新增 agent、修改 orchestrator、添加工具函数、调整项目结构时使用。确保所有开发遵循既定的目录约定和代码模式。
---

# Panda Brain 开发规范

## 项目架构

```
src/panda_brain/
├── config.py                # 配置 + get_model() 工厂
├── orchestrator/            # 调度入口（独立于子 agent）
│   ├── __init__.py
│   ├── agent.py             # orchestrator 定义
│   └── tools.py             # 委托工具（每个子 agent 一个函数）
├── agents/                  # 所有被编排的子 agent
│   ├── coder/
│   └── network/
└── main.py                  # CLI 入口
```

核心原则：`orchestrator/` 与 `agents/` 同级，目录结构直接表达调用关系。

## 新增子 Agent（三步）

### 第一步：创建 agent 包

在 `agents/` 下新建文件夹，文件夹名即 agent 名。包含三个文件：

**agent.py** — 定义 agent 实例：

```python
from pydantic_ai import Agent
from panda_brain.config import get_model

xxx_agent = Agent(
    get_model(),
    system_prompt="你是一个 XXX 专家。\n始终用中文回答。",
)
```

**tools.py** — 定义工具函数，通过装饰器注册：

```python
from panda_brain.agents.xxx.agent import xxx_agent

@xxx_agent.tool_plain
async def some_tool(param: str) -> str:
    """工具描述（LLM 根据此描述决定是否调用）。"""
    ...
```

- 不需要 `RunContext` 的工具用 `@agent.tool_plain`
- 需要依赖注入的工具用 `@agent.tool`，参数为 `ctx: RunContext[DepsType]`

**\_\_init\_\_.py** — 导出 agent 并触发工具注册：

```python
from panda_brain.agents.xxx.agent import xxx_agent
import panda_brain.agents.xxx.tools  # noqa: F401
__all__ = ["xxx_agent"]
```

### 第二步：注册到 orchestrator

在 `orchestrator/tools.py` 中添加委托函数：

```python
from panda_brain.agents.xxx import xxx_agent

@orchestrator.tool
async def delegate_to_xxx(ctx: RunContext, task: str) -> str:
    """描述何时应该委托给这个 agent（LLM 根据此描述路由）。"""
    result = await xxx_agent.run(task, usage=ctx.usage)
    return result.output
```

关键：`usage=ctx.usage` 确保 token 用量统一计量。

完成。orchestrator 通过委托函数的 docstring 自动识别新 agent，无需修改 orchestrator 的 prompt。

## 约定

### 命名

- agent 包名：小写，用途描述，如 `coder`、`network`、`writer`
- agent 变量名：`{name}_agent`，如 `coder_agent`
- 委托函数名：`delegate_to_{name}`，如 `delegate_to_coder`

### 模型

- 通过 `get_model()` 创建，默认使用全局配置
- 需要特定模型时：`get_model("qwen3-coder:latest")`
- 不要硬编码模型名到 agent 定义中

### 工具函数

- docstring 必须写清楚，LLM 靠它决定是否调用
- 异步函数（`async def`）
- 返回 `str`，包含有意义的结果描述
- 做好异常处理，不要让工具抛出未捕获的异常

### 职责分离

- orchestrator 的 system prompt **只做统筹**，不写各子 agent 的具体职责
- 路由决策靠委托函数的 **docstring** 驱动，新增 agent 不需要改 orchestrator 的 prompt
- 各子 agent 的 system prompt 自行定义行为细节（如"主动调用所有工具"）

### 不做的事

- 不提前创建 `deps.py`、`factory.py`、`shared/` — 等有实际需求再加
- 不在 agent 之间直接互相调用 — 统一由 orchestrator 编排
- 不把 orchestrator 放进 `agents/` 目录 — 它是调度层，不是子 agent
- 不在 orchestrator 的 prompt 中罗列子 agent 的功能描述
