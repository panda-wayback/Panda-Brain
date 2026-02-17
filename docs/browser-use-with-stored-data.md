# 存储标明来源 + browser-use 怎么用

## 1. 存储层：标明数据来自哪个网站

已在 bilibili_fetcher 写入时统一加上 **`source_site: "bilibili"`**：

- **bilibili_episodes**：每条 extra 含 `source_site`, `play_url`, `ssid`, `title` 等。
- **bilibili_danmaku**：每条 extra 含 `source_site`, `time_sec`, `danmaku_count`。

这样检索出来的每条记录都能知道「来自 B 站」，且番剧表里**已有播放链接**。

---

## 2. browser-use 自己会「发现去哪个网站」吗？

- browser-use **不会读我们的 LanceDB**，只会根据**你发给它的那一条任务文案**和**当前页面**做下一步。
- 所以「发现去 B 站」有两种方式：
  - **方式 A（推荐）**：**我们先查库**，根据 `source_site` 和 `play_url` **把「去哪个网站 / 打开哪个链接」写进任务**，再交给 browser-use 执行。
  - **方式 B**：任务里不写站点，只写「找骨王第一集」之类，由 browser-use 里的 LLM 凭常识推断去 bilibili。这样也能去 B 站，但不利用我们已存的数据和链接。

结论：**只要在「给 browser-use 的任务」里体现「来自哪个网站、有没有播放链接」，browser-use 就能按你的意图去对应网站或直接打开链接。** 发现逻辑做在我们这边（先查库），browser-use 负责执行。

---

## 3. 推荐用法：先查库，再组任务

因为存储里**已经标明来源网站**且**已有播放链接**，推荐流程是：

1. **用户说**：「找骨王第一集」/「播骨王第一集」。
2. **我们先查 LanceDB**（例如查 `bilibili_episodes`，或统一检索带 `source_site` 的表），用查询「骨王 第一集」。
3. **根据检索结果组任务**：
   - **若查到一条且 extra 里有 `play_url`、`source_site: "bilibili"`**  
     → 直接给 browser-use 任务：**「请用浏览器打开并播放: <play_url>」**，或把该链接交给点播/Playwright 打开（更快、更稳）。
   - **若只查到是 B 站相关、但没有对应集的链接**  
     → 给 browser-use 任务：**「我们库里有 B 站相关数据，请打开 bilibili.com 并搜索『骨王 第一集』，并打开第一集播放」**。
   - **若完全没查到**  
     → 原样把用户原话当任务给 browser-use，让它自己决定去哪个站、搜什么。
4. browser-use 只负责：**执行我们给它的那条任务**（打开某链接 / 去某站搜索等）。

这样：
- **来源网站**：靠存储里的 `source_site` 在查库时就知道是 B 站。
- **发现去哪个网站**：由我们根据 `source_site` 和是否有 `play_url` 决定，并在任务里写明「去 bilibili」或「打开 <url>」。
- **已有播放链接**：优先用 `play_url` 组成「打开并播放: <url>」的任务，减少 browser-use 盲目搜索。

---

## 4. 实现上的两种做法

- **轻量**：在探索入口（如 `browser_mcp/run_interactive.py`）里，调用 MCP 前先查 LanceDB（如 `lancedb.search("bilibili_episodes", user_input, limit=5)`），解析结果的 `extra` 里的 `source_site`、`play_url`；若有 `play_url` 则任务改为「打开并播放: <url>」，否则若 `source_site == "bilibili"` 则任务改为「去 bilibili.com 搜索 …」。
- **统一入口**：在主 orchestrator 或统一「探索」agent 里，先走「查库 → 按 source_site 与 play_url 组任务 → 再调 browser-use」，这样所有探索请求都能复用「存储标明来源 + 已有播放链接」的信息。

两种做法都依赖：**存储里已经标明来源网站（source_site）且番剧表里已有播放链接**；browser-use 只负责执行我们组装好的任务，这样既能「发现去 B 站」，又能充分利用已有链接。
