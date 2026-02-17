# 点播智能体 vs 浏览器 MCP 智能体：分工与选型

## 结论概览

| 场景 | 更合适的方式 | 本仓库对应 |
|------|--------------|------------|
| **确定性点播**：播这一集、从 5 分 30 秒播、快进 30 秒 | 直接 Playwright，脚本化控制 | `agents/playback` + `playwright_driver` |
| **探索型任务**：打开网页、点击、填表、执行 JS | Playwright MCP | `agents/browser_mcp` |

---

## 如何分别测试

1. **点播智能体（Playwright）**  
   ```bash
   .conda/bin/python src/panda_brain/agents/playback/run_interactive.py
   ```  
   说「骨王第三集」「快进 30 秒」等，由 playback 工具 + Playwright 执行。

2. **浏览器 MCP 智能体**  
   需 Node.js + npx，首次会拉取 `@playwright/mcp`。  
   ```bash
   .conda/bin/python src/panda_brain/agents/browser_mcp/run_interactive.py
   ```  
   输入自然语言任务，例如：「打开 bilibili.com」「点击登录按钮」。
