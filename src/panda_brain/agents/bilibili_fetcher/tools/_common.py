"""抓取工具共用：凭证、表名。"""

import os

from bilibili_api import Credential

# LanceDB 表名：番剧各集标题、BVID、播放链接，供按需查库返回链接
TABLE_EPISODES = "bilibili_episodes"


def get_credential() -> Credential:
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()
