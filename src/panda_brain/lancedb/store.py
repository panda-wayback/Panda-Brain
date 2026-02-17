"""LanceDB 向量存储基础实现：连接、建表、写入、语义检索、按 source 查重。
供 Deps.lancedb 或其它公共工具调用，各智能体只依赖「表名 + 文档格式」不关心本实现。"""

from __future__ import annotations

from typing import Any

import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

from panda_brain.config import settings

_db: lancedb.DBConnection | None = None
_embedding_model: Any = None
_DocumentSchema: type[LanceModel] | None = None


def get_db() -> lancedb.DBConnection:
    """获取 LanceDB 连接（单例，使用 settings.lancedb_path）。"""
    global _db
    if _db is None:
        _db = lancedb.connect(settings.lancedb_path)
    return _db


def _get_embedding_model():
    """懒加载 sentence-transformers embedding 模型（settings.lancedb_embedding_model）。"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = get_registry().get("sentence-transformers").create(
            name=settings.lancedb_embedding_model,
        )
    return _embedding_model


def _get_document_schema() -> type[LanceModel]:
    """返回默认文档 schema：text + vector + 可选 source、extra。"""
    global _DocumentSchema
    if _DocumentSchema is None:
        model = _get_embedding_model()

        class DocumentRow(LanceModel):
            text: str = model.SourceField()
            vector: Vector(model.ndims()) = model.VectorField()
            source: str | None = None
            extra: str | None = None

        _DocumentSchema = DocumentRow
    return _DocumentSchema


def ensure_table(table_name: str):
    """表不存在则用默认 schema 创建，存在则打开。返回表对象。"""
    db = get_db()
    if table_name in db.list_tables():
        return db.open_table(table_name)
    return db.create_table(table_name, schema=_get_document_schema(), exist_ok=True)


def add_documents(table_name: str, items: list[dict[str, Any]]) -> int:
    """向指定表写入文档。每条需含 "text"，可选 "source"、"extra"。自动向量化，返回写入条数。"""
    if not items:
        return 0
    table = ensure_table(table_name)
    rows = []
    for it in items:
        row: dict[str, Any] = {"text": it["text"]}
        if "source" in it:
            row["source"] = it.get("source")
        if "extra" in it:
            extra = it["extra"]
            row["extra"] = extra if isinstance(extra, str) else str(extra)
        rows.append(row)
    table.add(rows)
    return len(rows)


def search(table_name: str, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    """在指定表中语义检索。返回含 text、source、extra、_distance 的字典列表。"""
    table = ensure_table(table_name)
    results = table.search(query_text).limit(limit).to_list()
    return [dict(r) for r in results]


def list_tables() -> list[str]:
    """列出当前库下所有表名。"""
    return get_db().list_tables()


def table_has_source(table_name: str, source: str) -> bool:
    """该表是否已有 source 等于给定值的行；表不存在视为无。"""
    db = get_db()
    if table_name not in db.list_tables():
        return False
    try:
        table = db.open_table(table_name)
        rows = table.search().where(f"source = '{source}'").limit(1).to_list()
        return len(rows) > 0
    except Exception:
        return False


def has_matching_docs(table_name: str, query_text: str) -> bool:
    """表中是否存在与 query_text 语义匹配的文档（检索 1 条，有则 True）。表不存在或异常为 False。"""
    try:
        return len(search(table_name, query_text, limit=1)) >= 1
    except Exception:
        return False
