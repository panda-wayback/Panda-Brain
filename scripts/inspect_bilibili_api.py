"""查看 bilibili API 原始返回：搜索 + get_episode_list，便于根据真实字段判断季/类型。"""
import asyncio
import json
import sys

# 让 src 可导入
sys.path.insert(0, "src")

from bilibili_api import bangumi, search
from bilibili_api.search import SearchObjectType

from panda_brain.agents.bilibili_fetcher.utils import get_credential


async def main():
    cred = get_credential()

    # 1) 搜索「骨王」——看每条结果的完整字段
    print("=== search.search_by_type 骨王 (BANGUMI) 单条完整 keys ===")
    result = await search.search_by_type(
        keyword="骨王",
        search_type=SearchObjectType.BANGUMI,
        page=1,
        page_size=5,
    )
    for i, item in enumerate((result.get("result") or [])[:3]):
        print(f"\n--- 搜索结果 #{i+1} 所有 key ---")
        print(list(item.keys()))
        print("  title:", item.get("title"))
        print("  subtitle:", item.get("subtitle"))
        print("  season_id:", item.get("season_id"))
        print("  ssid:", item.get("ssid"))
        # 可能有 season_type, season_type_name 等
        for k in ("season_type", "season_type_name", "media_type", "type", "badge", "index_show"):
            if k in item:
                print(f"  {k}:", item.get(k))

    # 2) 骨王第一季 ssid=2576：get_episode_list 完整结构
    print("\n\n=== get_episode_list(ssid=2576) 顶层 keys ===")
    s = bangumi.Bangumi(ssid=2576, credential=cred)
    ep_data = await s.get_episode_list()
    print(list(ep_data.keys()))
    main_sec = ep_data.get("main_section") or {}
    print("\nmain_section keys:", list(main_sec.keys()))
    print("main_section.title:", main_sec.get("title"))
    print("main_section.type:", main_sec.get("type"))
    eps = main_sec.get("episodes") or []
    if eps:
        print("\n单集 episode 所有 keys:", list(eps[0].keys()))
        print("前 2 集 每条完整内容（仅部分字段）:")
        for i, ep in enumerate(eps[:2]):
            print(json.dumps({k: ep.get(k) for k in ("id", "title", "long_title", "badge", "badge_type", "badge_info", "share_copy")}, ensure_ascii=False, indent=2))

    # 3) section 存在时
    sections = ep_data.get("section") or []
    print("\nsection 数量:", len(sections))
    for j, sec in enumerate(sections[:3]):
        print(f"  section[{j}] keys:", list(sec.keys()), "title:", sec.get("title"), "type:", sec.get("type"))
        for ep in (sec.get("episodes") or [])[:1]:
            print("    首集 episode keys:", list(ep.keys()))

    # 4) 若 Bangumi 有 get_season_info / get_media_id 等，看是否有季号
    print("\n\n=== Bangumi 是否有 season 相关 API ===")
    for name in dir(s):
        if "season" in name.lower() or "media" in name.lower() or "info" in name.lower():
            print(" ", name)
    # 尝试获取更多元数据
    if hasattr(s, "get_media_id"):
        try:
            mid = await s.get_media_id()
            print("  get_media_id():", mid)
        except Exception as e:
            print("  get_media_id error:", e)
    if hasattr(s, "get_season_id"):
        try:
            sid = await s.get_season_id()
            print("  get_season_id():", sid)
        except Exception as e:
            print("  get_season_id error:", e)

    # 5) 搜索返回里是否有 season_type 等
    print("\n\n=== 搜索「骨王 第一季」第一条完整 item（看是否有季类型）===")
    r2 = await search.search_by_type(keyword="骨王 第一季", search_type=SearchObjectType.BANGUMI, page=1, page_size=3)
    for item in (r2.get("result") or [])[:1]:
        print(json.dumps(item, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
