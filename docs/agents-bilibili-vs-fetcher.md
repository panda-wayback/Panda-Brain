# B 站相关智能体：bilibili_fetcher

## bilibili_fetcher（抓取智能体）

- **职责**：抓取 B 站数据并写入 LanceDB（播放链接表 `bilibili_episodes`、弹幕表 `bilibili_danmaku`），供后续从库查询；解析番剧名到播放链接（`resolve_bangumi_to_bvid`）。
- **用户说「骨王」时**：可调用 `fetch_and_store_bangumi_play_links(keyword)` 等入库，或仅解析单集播放链接供 browser_mcp 打开。
- **browser_mcp** 会调用 bilibili_fetcher 的解析能力（get_bangumi_play_url）拿到播放 URL，再用 Playwright MCP 打开与跳转。

## 使用建议

- 要**播放链接、入库、供后续查询**：用 bilibili_fetcher（`run_interactive.py` 或 orchestrator 委托）。
- 要**打开番剧页、从第 N 分钟播**：用 browser_mcp（内部会调 get_bangumi_play_url）。
