"""Playwright 播放端：固定单窗口单标签、持久化用户数据（保留 B 站登录）、打开/seek。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright

# 持久化用户数据目录：首次启动后在该窗口登录 B 站一次，之后会保持大会员登录
_USER_DATA_DIR = Path.home() / ".config" / "panda_brain_playback"

_driver: PlaywrightDriver | None = None
_lock = asyncio.Lock()


async def get_driver() -> PlaywrightDriver:
    """获取单例 Playwright 播放端；首次调用时创建并 launch 浏览器。"""
    global _driver
    async with _lock:
        if _driver is None:
            _driver = PlaywrightDriver()
            await _driver._ensure()
        return _driver


def _reset_driver() -> None:
    """测试或显式关闭后重置单例。"""
    global _driver
    _driver = None


class PlaywrightDriver:
    """固定单窗口单标签、持久化 profile（保留登录），open/seek 均操作同一标签。"""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._headless = False  # 可见窗口便于用户观看与登录

    async def _ensure(self) -> None:
        """若无有效 page 则 launch 持久化浏览器（同目录保留 Cookie/登录）并复用单页。"""
        if self._page is not None and not self._page.is_closed():
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("请安装 playwright 并执行: playwright install chromium")
        self._playwright = await async_playwright().start()
        _USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(_USER_DATA_DIR.resolve()),
            headless=self._headless,
            no_viewport=True,
        )
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        await self._maximize_window()

    async def _maximize_window(self) -> None:
        """通过 CDP 将浏览器窗口设为最大化（macOS 上 --start-maximized 无效）。"""
        try:
            cdp = await self._context.new_cdp_session(self._page)
            res = await cdp.send("Browser.getWindowForTarget")
            window_id = res.get("windowId")
            if window_id is not None:
                await cdp.send(
                    "Browser.setWindowBounds",
                    {"windowId": window_id, "bounds": {"windowState": "maximized"}},
                )
        except Exception:
            pass

    async def open(self, url: str, start_time_sec: int | None = None) -> str:
        """打开 B 站播放链接；start_time_sec 不为空时在 URL 加 ?t= 或 &t= 从该秒开始播。"""
        url = (url or "").strip()
        if not url:
            return "请提供播放链接。"
        await self._ensure()
        if start_time_sec is not None and start_time_sec >= 0:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}t={start_time_sec}"
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self._page.wait_for_selector("video", state="attached", timeout=15_000)
            await self._fullscreen_video()
        except Exception as e:
            return f"打开页面失败: {e}"
        return f"已在播放器打开：{url}"

    async def _fullscreen_video(self) -> None:
        """尝试将视频设为全屏（优先点击 B 站全屏按钮，备选 video.requestFullscreen）。"""
        try:
            # 先悬停视频区域以显示控制栏
            video_el = await self._page.query_selector("video")
            if video_el:
                await video_el.hover()
                await asyncio.sleep(0.3)
            # 点击 B 站全屏按钮（.bpx-player-ctrl-full 真全屏 / .bpx-player-ctrl-wide 宽屏）
            btn = await self._page.query_selector(
                ".bpx-player-ctrl-full, "
                ".bpx-player-ctrl-wide, "
                ".bilibili-player-iconfont-fullscreen, "
                "[class*='fullscreen']"
            )
            if btn:
                await btn.click(timeout=2000)
                return
            # 2) 备选：video.requestFullscreen（部分站点需用户手势，可能被拦截）
            await self._page.evaluate(
                """async () => {
                    const v = document.querySelector('video');
                    const el = v && v.closest('.bilibili-player-video-wrap') || v;
                    if (!el) return;
                    const req = el.requestFullscreen || el.webkitRequestFullscreen || el.webkitEnterFullscreen;
                    if (req) await req.call(el);
                }"""
            )
        except Exception:
            pass

    async def seek_relative(self, delta_sec: int) -> str:
        """快进或倒退若干秒（正=快进，负=倒退）。需已打开播放页。"""
        await self._ensure()
        if self._page.is_closed():
            return "播放页已关闭，请先重新播放。"
        try:
            result = await self._page.evaluate(
                """(delta) => {
                    const v = document.querySelector('video');
                    if (!v) return { ok: false, msg: '未找到播放器' };
                    v.currentTime = Math.max(0, Math.min(v.duration, v.currentTime + delta));
                    v.play();
                    return { ok: true, currentTime: v.currentTime };
                }""",
                delta_sec,
            )
        except Exception as e:
            return f"执行快进/倒退失败: {e}"
        if not result.get("ok"):
            return result.get("msg", "未找到播放器，请先播放。")
        t = result.get("currentTime", 0)
        return f"已{('快进' if delta_sec > 0 else '倒退')} {abs(delta_sec)} 秒，当前约 {int(t)} 秒。"

    async def seek_absolute(self, position_sec: int) -> str:
        """跳到指定秒数位置播放。需已打开播放页。"""
        await self._ensure()
        if self._page.is_closed():
            return "播放页已关闭，请先重新播放。"
        try:
            result = await self._page.evaluate(
                """(pos) => {
                    const v = document.querySelector('video');
                    if (!v) return { ok: false, msg: '未找到播放器' };
                    v.currentTime = Math.max(0, Math.min(v.duration, pos));
                    v.play();
                    return { ok: true, currentTime: v.currentTime };
                }""",
                position_sec,
            )
        except Exception as e:
            return f"执行跳转失败: {e}"
        if not result.get("ok"):
            return result.get("msg", "未找到播放器，请先播放。")
        return f"已跳到 {position_sec} 秒。"

    async def close(self) -> None:
        """关闭浏览器并重置单例。"""
        global _driver
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._playwright = None
        _driver = None  # noqa: PLW0603
