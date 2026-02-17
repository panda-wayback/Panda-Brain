# 浏览器 MCP 智能体（browser_mcp）

点播与浏览器探索均由 `agents/browser_mcp` 承担：通过 get_bangumi_play_url 解析番剧播放链接，再配合 Playwright MCP（browser_navigate、browser_evaluate）打开页面、跳转进度。

## 测试

需 Node.js + npx，首次会拉取 `@playwright/mcp`。

```bash
.conda/bin/python src/panda_brain/agents/browser_mcp/run_interactive.py
```

示例：「骨王第十集」「从第6分钟开始播放」「打开 bilibili.com」。
