# 点播智能体 · Playwright 方案分析

**已实现**：`agents/playback/playwright_driver.py` 与 `tools.py` 中 play/seek 已接入；首次 `play` 时 launch 浏览器，后续 seek 复用同一 page。需安装 `playwright` 并执行 `playwright install chromium`。

## 目标

用 Playwright 替代 `webbrowser.open`，实现：

- **打开链接并从某时刻播**：`page.goto(url?t=秒数)` 或打开后设 `video.currentTime`
- **快进 / 倒退**：在已打开页内执行 `video.currentTime += delta`，真正生效
- **跳到某时刻**：`video.currentTime = position_sec`，无需刷新页

## B 站页面与 DOM

- 番剧播放页（如 `https://www.bilibili.com/bangumi/play/epXXXXX`）内嵌标准 HTML5 `<video>`。
- 可通过 `document.querySelector("video")` 获取元素，使用 `HTMLMediaElement`：
  - `currentTime` 读/写（秒）
  - `play()` / `pause()`
  - `duration` 总时长
- 若播放器在 iframe 内，需先 `page.frame_locator(...)` 或 `frame.evaluate` 再操作；当前先按主文档内 `video` 设计，若遇 iframe 再适配。

## 架构

```
点播智能体 (playback_agent)
    ↓ 调用
play/tools.py 中的 play、seek_relative、seek_absolute
    ↓ 调用
playback/playwright_driver.py：单例或显式传入的「播放端」
    - open(url, start_time_sec=None)  → 打开页并可选 t= 参数
    - seek_relative(delta_sec)        → page.evaluate 改 video.currentTime
    - seek_absolute(position_sec)    → 同上
```

- **生命周期**：交互式场景下常驻一个 browser + 一个 page，避免每次「播」都 launch；首次 play 时 launch，后续 seek 复用同一 page。关闭 run_interactive 时再 close。
- **并发**：单用户、单会话下同一时刻只有一个播放页，driver 持有一个 `page` 即可；多会话可扩展为「每会话一个 driver」。

## 依赖

- `playwright>=1.40`，并执行一次 `playwright install chromium`（或使用系统已有 Chromium）。
- 放入 `pyproject.toml` 的 `dependencies` 或可选依赖组 `[project.optional-dependencies] playback`。

## 接口设计（driver）

| 方法 | 含义 | 说明 |
|------|------|------|
| `open(url, start_time_sec=None)` | 打开播放页，可选从某秒开始 | 有 start_time_sec 时 URL 加 `?t=...` 或打开后设 currentTime |
| `seek_relative(delta_sec)` | 快进/倒退 | `currentTime += delta_sec`，再 `play()` |
| `seek_absolute(position_sec)` | 跳到某秒 | `currentTime = position_sec`，再 `play()` |
| `close()` | 关闭浏览器 | 交互结束时调用 |

若当前没有已打开页面或页面已关闭，`seek_*` 返回「请先播放」类提示。

## 与现有工具的衔接

- **play**：由 `webbrowser.open` 改为调用 driver 的 `open()`；若 driver 未初始化则 `playwright.chromium.launch()` + `new_page()`，再 `goto`。
- **seek_relative / seek_absolute**：由「只写记录」改为先调 driver 的对应方法，再写点播记录；若 driver 无有效 page，则保留当前「仅记录」行为并提示。

## 风险与注意点

1. **选择器**：B 站改版可能导致 `querySelector("video")` 失效或需进 iframe，届时在 driver 内改选择器或切 frame 即可。
2. **登录/会员**：Playwright 默认无登录态；若需会员清晰度或权限，可后续加 `storage_state` 复用已登录 profile。
3. **资源**：常驻 Chromium 会占内存；若仅偶尔点播，可改为「每次 play 时 launch、闲置一段时间后 close」的折中策略。
