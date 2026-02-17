---
name: panda-brain-config-files
description: Panda Brain 配置文件编写规范。在新增或修改 agent 的 system_prompt.yaml、.env 等配置时使用。确保配置与 load_system_prompt 等加载逻辑一致。
---

# 配置文件编写规范

## 1. agent system_prompt.yaml

### 位置与加载

- 路径：`agents/<agent_name>/system_prompt.yaml`
- 加载：`panda_brain.utils.prompt_loader.load_system_prompt(path, default=None)`
- 用法：`load_system_prompt(Path(__file__).parent / "system_prompt.yaml", default=...)`

### 结构（role + rules + footer）

```yaml
# 顶部注释：简要说明该 agent 的职责

role: |
  你是 XXX 智能体：身份说明、可用工具与行为概述。

rules:
  - when: 用户说/做 XXX（具体触发条件）
    action: |
      调用 tool_A 做 A；再调用 tool_B 做 B。参数说明与约束。
    example: '用户输入示例 → 工具调用示例'

  - when: 另一触发条件
    action: |
      具体动作说明。
    example: '示例（可选）'

footer: 始终用中文回答。
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `role` | 是 | 身份 + 工具概览。用 `|` 多行。 |
| `rules` | 是 | 列表，每项含 `when`、`action`、`example`（可选）。 |
| `when` | 是 | 触发条件，简洁描述用户意图或场景。 |
| `action` | 是 | 应执行的动作，包含工具名、参数、顺序。 |
| `example` | 否 | 简短示例，帮助模型理解调用方式。 |
| `footer` | 否 | 收尾指令（如「始终用中文回答」）。 |

### 拼装逻辑

`load_system_prompt` 会：

1. 取 `role`
2. 遍历 `rules`，拼成 `1. when：action。示例：example。`（无 example 则省略示例部分）
3. 取 `footer`
4. 用 `\n\n` 连接

### 编写建议

- **when**：覆盖典型用户表达，含同义说法（如「弟N集」=「第N集」）
- **action**：明确工具名、参数顺序、异常处理（如「拿链接失败时先重试」）
- **example**：尽量简短，体现输入→工具调用映射
- **footer**：统一收尾（语言、风格等）

---

## 2. .env 环境变量

- 项目用 `pydantic-settings`，`PANDA_` 前缀。
- 常用项：`PANDA_OLLAMA_BASE_URL`、`PANDA_DEFAULT_MODEL`、`PANDA_LANCEDB_PATH`
- 新增配置时在 `panda_brain.config.Settings` 中定义，并通过 `.env` 或环境变量覆盖。

---

## 3. 其他配置

- `pyproject.toml`：依赖、脚本入口
- `requirements.txt`：与 pyproject.toml 同步
- 新增 agent 时参考现有 `system_prompt.yaml` 结构，保持与 `load_system_prompt` 兼容
