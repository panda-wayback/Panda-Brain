"""兼容层：LanceDB 实现已迁至 panda_brain.lancedb，此处仅再导出。"""

from panda_brain.lancedb import (
    add_documents,
    ensure_table,
    get_db,
    list_tables,
    search,
    table_has_source,
)

__all__ = [
    "get_db",
    "ensure_table",
    "add_documents",
    "search",
    "list_tables",
    "table_has_source",
]
