import socket
import time

import httpx

from panda_brain.agents.network.agent import network_agent


@network_agent.tool_plain
async def get_local_ip() -> str:
    """获取本机局域网 IP 地址。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"本机局域网 IP: {ip}"
    except Exception as e:
        return f"获取局域网 IP 失败: {e}"


@network_agent.tool_plain
async def get_public_ip() -> str:
    """获取本机公网 IP 地址。"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            ip = resp.json()["ip"]
            return f"本机公网 IP: {ip}"
    except Exception as e:
        return f"获取公网 IP 失败: {e}"


@network_agent.tool_plain
async def speed_test() -> str:
    """测试当前网络的下载速度和延迟。"""
    results: list[str] = []

    # 测试延迟 (ping)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            start = time.monotonic()
            await client.get("https://www.baidu.com")
            latency_ms = (time.monotonic() - start) * 1000
            results.append(f"网络延迟: {latency_ms:.0f}ms (baidu.com)")
    except Exception as e:
        results.append(f"延迟测试失败: {e}")

    # 测试下载速度 (用 Cloudflare 的 100MB 测试文件，只下载前 10MB)
    try:
        url = "https://speed.cloudflare.com/__down?bytes=10000000"
        async with httpx.AsyncClient(timeout=30) as client:
            start = time.monotonic()
            resp = await client.get(url)
            elapsed = time.monotonic() - start
            size_mb = len(resp.content) / (1024 * 1024)
            speed_mbps = (size_mb * 8) / elapsed
            results.append(f"下载速度: {speed_mbps:.1f} Mbps ({size_mb:.1f}MB / {elapsed:.1f}s)")
    except Exception as e:
        results.append(f"下载测速失败: {e}")

    return "\n".join(results)
