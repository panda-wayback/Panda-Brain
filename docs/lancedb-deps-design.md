# LanceDB 作为「基础」通过 deps 注入 — 设计与可行性

## 1. 你的目标（理解）

- **LanceDB 是所有智能体的基础**：各 agent 都应能「查向量库」找数据，而不是只有「存储专家」能碰。
- **通过上下文调用**：希望智能体通过 RunContext（依赖注入）拿到 LanceDB 能力，而不是在代码里直接 `import storage`。
- **是否「实现一个智能体，然后实例化在 deps 中」**：需要先厘清「deps 里放什么」。

---

## 1.5 直接回答两个常见疑问

### Storage agent 在哪里？

- **Storage agent 还是一个普通的子 agent**，和 bilibili、coder、network 一样，在 `agents/storage/` 里。
- **它不在 deps 里**。deps 里只有「LanceDB 服务实例」（能力），没有「某个 agent」。
- 关系是：
  - **deps** = 装着「LanceDB 能力」的袋子，每次跑任何 agent 时都会传进去（`run(..., deps=deps)`）。
  - **Storage agent** = 一个专门负责「存/取/列表」的专家；当用户说「把这段话存起来」或「查一下笔记」时，orchestrator 会 **委托给** storage agent（`delegate_to_storage`），storage agent 跑的时候拿到的也是**同一份 deps**，它的工具里用 `ctx.deps.lancedb.search(...)` 等来真正读写。
- 所以：**LanceDB 能力在 deps 里，storage agent 是「会用这个能力的其中一个 agent」**；你也可以选择不要 storage agent，让 orchestrator 自己带存/取工具（见下文方案乙）。

### 每个智能体可以「自动」从 LanceDB 拿数据、自动存数据么？

要区分两件事：

1. **「可以」拿/存**（有能力）  
   - 可以。只要某个 agent 声明了 `deps_type=Deps`，并且在它的**某个工具**里写了「查库/写库」的逻辑（调用 `ctx.deps.lancedb.search(...)` 或 `add_documents(...)`），那这个 agent 就**具备**从 LanceDB 拿数据、存数据的能力。
   - 例如：给 bilibili agent 加一个工具「查用户笔记里和当前视频相关的内容」，工具里调 `ctx.deps.lancedb.search("notes", query)`，那 bilibili 就能在回答前先查库。

2. **「自动」**（不用人说要存/查，就会存/查）  
   - **不会完全自动**。存/取必须通过「工具被 LLM 调用」才会发生。也就是说：
     - 要么用户说了「存一下」「查一下」→ orchestrator（或 storage agent）的**存/取工具**被调用；
     - 要么某个子 agent 的 prompt/工具设计成「回答前先查库」→ 该 agent 的**查库工具**被调用。
   - 所以：**每个智能体可以（在配有对应工具的前提下）从 LanceDB 拿数据、存数据**；但不会「不经过任何工具就自动」拿/存，一定是「某个 agent 的某个工具」被调用时才发生。

总结一句：**deps 让所有 agent 都能「拿到」LanceDB 能力；每个 agent 要真的去拿/存数据，需要在自己的工具里用 `ctx.deps.lancedb`，并由 LLM 在合适的时候调用这些工具。**

| 东西 | 放在哪 | 谁用、怎么用 |
|------|--------|----------------|
| **LanceDB 服务**（search / add_documents / list_tables） | **deps 里**，例如 `Deps(lancedb=LanceDBService())` | 任何 agent 在工具里写 `ctx.deps.lancedb.xxx(...)` 就能用 |
| **Storage agent** | **agents/storage/**，和 bilibili/coder 同级 | 一个「存/取专家」子 agent；被 orchestrator 委托时，拿到的也是同一份 `ctx.deps`，工具内部调 `ctx.deps.lancedb` |
| **Orchestrator 的存/取工具**（若采用方案乙） | **orchestrator/tools.py** | 编排器自己的工具，内部 `ctx.deps.lancedb.xxx`，用户说存/查时由编排器直接执行，不经过 storage agent |

---

## 2. 两种理解

### 2.1 理解 A：deps 里放「LanceDB 服务实例」（推荐）

- **deps** 里放的是**服务/能力对象**，不是 agent。
- 例如：`Deps(lancedb=LanceDBService())`，其中 `LanceDBService` 提供 `search(table, query, limit)`、`add_documents(table, items)`、`list_tables()`。
- 所有 agent（orchestrator + 各子 agent）声明 `deps_type=Deps`，工具里用 `ctx.deps.lancedb.search(...)` 等。
- **不需要**在 deps 里放「storage agent 实例」；LanceDB 是基础设施，以「服务」形式注入即可。

### 2.2 理解 B：deps 里放「storage agent 实例」

- 即：`Deps(storage_agent=storage_agent)`，其他 agent 需要查库时通过 `ctx.deps.storage_agent.run(...)` 去调 storage agent。
- 问题：
  - 违反当前规范「不在 agent 之间直接互相调用」；
  - 每次查库都是一次完整子 agent run，开销大、延迟高；
  - 类型和用法都更复杂（要拼 prompt、解析 output）。
- **不推荐**。

结论：**采用理解 A**：deps 里放 LanceDB **服务实例**（封装 add/search/list_tables），不放在 deps 里放 agent。

---

## 3. 推荐设计（LanceDB 作为 deps 中的「基础」）

### 3.1 概念关系

```
main.py
  └─ 构造 deps = Deps(lancedb=LanceDBService())   # 单例服务，内部用现有 lancedb_store 逻辑
  └─ orchestrator.run(..., deps=deps)

orchestrator (deps_type=Deps)
  ├─ 工具里可调用 ctx.deps.lancedb.search / add_documents / list_tables
  ├─ 委托时：xxx_agent.run(task, deps=ctx.deps, usage=ctx.usage)  # 把同一 deps 传下去
  └─ 子 agent 若有「查库」需求，其工具同样用 ctx.deps.lancedb.xxx

子 agent（coder / bilibili / network / storage 等）
  └─ 统一 deps_type=Deps（与 orchestrator 一致）
  └─ 需要查库的工具：@agent.tool，ctx: RunContext[Deps]，内部 ctx.deps.lancedb.search(...)
  └─ 不需要查库的工具：可继续用 @agent.tool_plain，或 @agent.tool 但不使用 ctx.deps
```

- **LanceDB**：以「服务」形式存在于 `Deps` 中，所有 agent 通过**同一 deps 实例**、通过**上下文**使用，符合「所有智能体都通过上下文调用 LanceDB」。
- **Storage agent** 是否保留可选：
  - **方案甲**：保留 storage agent，其工具内部改为 `ctx.deps.lancedb.xxx`，orchestrator 仍通过 `delegate_to_storage` 把「存/取/列表」任务交给它；同时其他 agent 若需要也可在自己的工具里用 `ctx.deps.lancedb`。
  - **方案乙**：不再设独立 storage agent；orchestrator 自己提供 `lancedb_add` / `lancedb_search` / `lancedb_list_tables` 三个工具（内部用 `ctx.deps.lancedb`），所有「查库/写库」由编排器直接完成，子 agent 只在需要时在自己的工具里用 `ctx.deps.lancedb`。  
  两种都可行，方案乙更简单、少一层委托。

---

## 4. 实现可行性

### 4.1 Pydantic-AI 能力（已满足）

- **deps 定义**：`Deps` 用 dataclass（或 Pydantic Model），字段 `lancedb: LanceDBService`。
- **Agent**：`Agent(..., deps_type=Deps)`；工具签名 `ctx: RunContext[Deps]`，使用 `ctx.deps.lancedb`。
- **入口**：`agent.run(prompt, deps=deps)`，deps 在 main 里构造一次即可。
- **委托时传递 deps**：`result = await xxx_agent.run(task, deps=ctx.deps, usage=ctx.usage)`，子 agent 与 orchestrator 使用同一 deps 类型、同一实例，完全支持。

### 4.2 需要改动的点

| 项目 | 说明 |
|------|------|
| **deps 定义** | 新增 `panda_brain.deps`（或 `orchestrator/deps.py`）：`Deps` 类 + `LanceDBService` 类（封装现有 `lancedb_store` 的 add_documents/search/list_tables，可选封装 ensure_table/get_db 等）。 |
| **入口** | `main.py` 中构造 `deps = Deps(lancedb=LanceDBService())`，`orchestrator.run(..., deps=deps)`。 |
| **Orchestrator** | `Agent(..., deps_type=Deps)`；委托工具中 `xxx_agent.run(task, deps=ctx.deps, usage=ctx.usage)`；若采用方案乙，为编排器增加三个工具，内部调用 `ctx.deps.lancedb.*`。 |
| **子 Agent** | 全部改为 `deps_type=Deps`；需要 LanceDB 的工具从 `@agent.tool_plain` 改为 `@agent.tool`，签名加 `ctx: RunContext[Deps]`，内部用 `ctx.deps.lancedb`。不需要 LanceDB 的工具可保持 `tool_plain` 或仍用 `tool` 但不使用 deps。 |
| **Storage agent** | 若保留（方案甲）：其工具改为 `@storage_agent.tool` + `ctx.deps.lancedb.*`；若移除（方案乙）：删除 storage agent，由 orchestrator 的三种工具替代。 |

### 4.3 可行性结论

- **技术上完全可行**：Pydantic-AI 的 deps 与 `run(deps=)` 支持上述用法，子 agent 与 orchestrator 共享同一 `Deps` 类型和实例即可。
- **设计上更清晰**：LanceDB 作为「基础」只以服务形式出现在 deps 中，所有智能体通过上下文使用，不引入「在 deps 里放 agent」的复杂度和规范冲突。
- **建议**：采用 **deps 里放 LanceDB 服务实例**，**不**在 deps 里实例化 storage agent；是否保留 storage agent 为可选（方案甲/乙），可按你偏好选一种落地。

---

## 5. 小结

- **「通过上下文调用 LanceDB」**：用 `Deps(lancedb=LanceDBService())` + 各 agent `deps_type=Deps`，在工具里用 `ctx.deps.lancedb` 即可实现。
- **「实现一个智能体然后实例化在 deps 中」**：不推荐把 agent 放进 deps；推荐在 deps 里放 **LanceDB 服务实例**，由各 agent（含 orchestrator）通过 RunContext 统一使用。
- **实现可行性**：高；主要工作是引入 `Deps`/`LanceDBService`、统一 deps 类型、委托时传递 `ctx.deps`，以及按方案甲或乙处理 storage agent。

如果你愿意按其中一种方案落地，我可以按当前项目结构给出具体改动的文件列表和代码片段（deps 定义、main、orchestrator、子 agent 的修改要点）。

---

## 6. 已落地实现（方案乙）

当前项目已按**方案乙**实现：

- **`panda_brain.deps`**：`Deps`（含 `lancedb: LanceDBService`）、`LanceDBService`、`create_deps()`。
- **入口**：`main.py` 中 `deps = create_deps()`，`orchestrator.run(..., deps=deps)`。
- **Orchestrator**：`deps_type=Deps`；提供 `lancedb_add`、`lancedb_search`、`lancedb_list_tables` 三个工具（内部 `ctx.deps.lancedb.*`）；委托时 `xxx_agent.run(task, deps=ctx.deps, usage=ctx.usage)`。
- **子 agent**（coder、network、bilibili）：均声明 `deps_type=Deps`，委托时传入同一 `ctx.deps`；后续若某 agent 需要在自己的工具里查库，可写 `@agent.tool` + `ctx.deps.lancedb.search(...)` 等。
- **Storage agent**：已移除，存/取由编排器上述三工具完成。
