"""编排器工具包：按类别加载，确保注册到 orchestrator。

分类：
- lancedb: 向量库写/查/列表
- delegate: 委托给 bilibili_fetcher、browser_mcp
"""

import panda_brain.orchestrator.tools.lancedb  # noqa: F401
import panda_brain.orchestrator.tools.delegate  # noqa: F401
