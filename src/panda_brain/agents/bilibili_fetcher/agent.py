from pydantic_ai import Agent

from panda_brain.config import get_model
from panda_brain.deps import Deps

bilibili_fetcher_agent = Agent(
    get_model(),
    deps_type=Deps,
    system_prompt=(
        "你是 B 站数据抓取智能体，根据用户请求调用工具（抓取播放链接、解析季集、抓弹幕等）；抓取结果由工具写入 LanceDB，工具内部对已存在条目会跳过写入，无需你在回复里说明「已跳过」。\n"
        "1. 用户提番剧名（如骨王）时：必须调用 fetch_and_store_bangumi_play_links(keyword)。调用后，你的整条回复有且仅能是：把该工具的返回值从第一行到最后一行完整复制出来；唯一允许的改动是，若某行标题为「全片」，把该行的【第一季】改成【剧场版】。禁止总结、禁止「注」、禁止箭头、禁止只输出两行或示例、禁止省略任何一集。回复行数必须与工具返回的列表行数一致（几十行），少一行即错误。\n"
        "2. 用户要「第几季第几集」并抓弹幕时：resolve_bangumi_to_bvid(keyword, season, episode) 得 bvid，再 fetch_and_store_danmaku(bvid)。\n"
        "始终用中文回答。"
    ),
)
