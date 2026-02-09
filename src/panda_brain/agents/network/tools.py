import socket

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
