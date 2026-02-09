# Panda Brain

基于 [Pydantic AI](https://ai.pydantic.dev/) 的多智能体系统，使用本地 Ollama 作为 LLM 后端。

## 架构

```
orchestrator (编排器)
├── 直接回答一般性问题
└── delegate_to_coder ──→ coder_agent (代码专家)
                              └── run_shell_command (执行本地命令)
```

- **Orchestrator** — 入口 agent，理解用户意图，路由到对应的专家 agent 或直接回答
- **Coder Agent** — 编程专家，具备本地 shell 命令执行能力

扩展新 agent 只需在 `agents/` 下新建包，然后在 `orchestrator/tools.py` 中添加对应的委托工具。

## 前置要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- [Ollama](https://ollama.com/) 运行中，并已拉取所需模型

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 确保 Ollama 运行中并拉取模型
ollama pull qwen3

# 3. （可选）自定义配置
cp .env.example .env
# 编辑 .env 修改模型或 Ollama 地址

# 4. 启动
uv run panda-brain
```

## 配置

通过环境变量或 `.env` 文件配置，所有变量以 `PANDA_` 为前缀：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PANDA_DEFAULT_MODEL` | `qwen3:latest` | Ollama 模型名 |
| `PANDA_OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 服务地址 |

## 项目结构

```
src/panda_brain/
├── config.py                   # 配置管理 + 模型工厂
├── orchestrator/               # 编排器 (系统入口，调度子 agent)
│   ├── agent.py                # orchestrator 定义
│   └── tools.py                # 委托工具 (路由到子 agent)
├── agents/                     # 子 agent (被 orchestrator 调用)
│   └── coder/                  # 代码专家 agent
│       ├── agent.py            # agent 定义
│       └── tools.py            # shell 执行等工具
└── main.py                     # CLI 入口
```

- `orchestrator/` — 系统调度入口，独立于子 agent
- `agents/` — 所有被编排的专家 agent，每个 agent 一个包
