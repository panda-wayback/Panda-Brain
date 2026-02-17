"""B 站抓取工具包：仅保留「全部链接入库」与「按需返回单集链接」两类能力。

- resolve: 按需返回单集播放链接（get_play_url，先查库再解析）
- episode: 抓取整部动漫全部播放链接并写入 LanceDB（fetch_and_store_bangumi_play_links）
"""

import panda_brain.agents.bilibili_fetcher.tools.episode  # noqa: F401
import panda_brain.agents.bilibili_fetcher.tools.resolve  # noqa: F401
