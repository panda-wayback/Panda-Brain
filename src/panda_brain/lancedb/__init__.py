"""LanceDB 公共模块：向量库连接、建表、写入、语义检索、按 source 查重、行 extra 解析。
各智能体通过 Deps.lancedb 或本模块直接调用，只关心表名与文档格式，不关心底层实现。"""

from panda_brain.lancedb.row import parse_extra
from panda_brain.lancedb.store import (
    add_documents,
    ensure_table,
    get_db,
    has_matching_docs,
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
    "has_matching_docs",
    "parse_extra",
]
