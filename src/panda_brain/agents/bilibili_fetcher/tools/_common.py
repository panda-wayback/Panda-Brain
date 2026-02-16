"""抓取工具共用：凭证、HTML 清理、表名与常量。"""

import os
import re

from bilibili_api import Credential

# LanceDB 表名
TABLE_DANMAKU = "bilibili_danmaku"
TABLE_COMMENTS = "bilibili_comments"
TABLE_EPISODES = "bilibili_episodes"  # 番剧各集标题、BVID、播放链接，供后续从库查询

# 弹幕单条最多写入的字符（避免过长）
DANMAKU_TEXT_MAX = 200
# 按秒聚合时，该秒合并后的弹幕文本最大长度（再长则截断）
DANMAKU_MERGE_PER_SEC_MAX = 800


def get_credential() -> Credential:
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s) if s else ""
