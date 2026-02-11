import os

from bilibili_api import Credential, comment
from bilibili_api.comment import CommentResourceType, OrderType
from bilibili_api.utils.aid_bvid_transformer import bvid2aid

from panda_brain.agents.bilibili.agent import bilibili_agent


def _get_credential() -> Credential:
    sessdata = os.environ.get("BILIBILI_SESSDATA", "")
    return Credential(sessdata=sessdata) if sessdata else Credential()


@bilibili_agent.tool_plain
async def get_top_comments(bvid: str, top_n: int = 10) -> str:
    """获取视频的高赞评论，用于丰富视频资料。传入 bvid（如 BV1Ks411S7co），返回点赞最多的前 top_n 条评论。"""
    if top_n <= 0 or top_n > 50:
        top_n = 10
    try:
        aid = bvid2aid(bvid)
        cred = _get_credential()
        result = await comment.get_comments(
            oid=aid,
            type_=CommentResourceType.VIDEO,
            page_index=1,
            order=OrderType.LIKE,
            credential=cred,
        )
        replies = result.get("replies") or []
        lines: list[str] = []
        for i, r in enumerate(replies[:top_n], 1):
            msg = (r.get("content") or {}).get("message", "")
            like = r.get("like", 0)
            lines.append(f"{i}. [赞{like}] {msg[:200]}{'...' if len(msg) > 200 else ''}")
        return f"高赞评论（{bvid}）:\n" + "\n\n".join(lines) if lines else "暂无评论。"
    except Exception as e:
        return f"获取失败: {e}"
