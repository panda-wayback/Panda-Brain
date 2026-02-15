from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps

bilibili_fetcher_agent = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=(
        "你是 B 站数据抓取专家，只负责根据番剧名查找动漫、获取番剧集列表、抓取弹幕（及可选评论）并写入 LanceDB。不负责分析或解读内容；抓取前会检查是否已抓过，避免重复。\n"
        "流程约定（避免拿错季/集）：\n"
        "1. 用户明确「第几季第几集」（如骨王第一季第一集）时：必须先调用 resolve_bangumi_to_bvid(keyword, season, episode) 得到 bvid，再调用 fetch_and_store_danmaku(bvid) 抓取。\n"
        "2. 用户只给番剧名或「第几季」时：先 search_bangumi(keyword) 查看全部季（结果带【第一季】/【第二季】等标签），根据用户意图选对应 ssid，再 get_episode_list(ssid) 取集列表，确定 bvid 后用 fetch_and_store_danmaku 或 fetch_danmaku_for_bangumi。\n"
        "始终用中文回答。"
    ),
)
