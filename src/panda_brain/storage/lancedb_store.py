"""LanceDB 向量存储：连接、建表、写入、语义检索。供各 agent 或工具直接调用。"""

from __future__ import annotations

from typing import Any

import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

from panda_brain.config import settings

# 单例连接与 embedding 模型，懒加载
_db: lancedb.DBConnection | None = None
_embedding_model: Any = None
_DocumentSchema: type[LanceModel] | None = None


def get_db() -> lancedb.DBConnection:
    """获取 LanceDB 连接（单例）。"""
    global _db
    if _db is None:
        _db = lancedb.connect(settings.lancedb_path)
    return _db


def _get_embedding_model():
    """懒加载 sentence-transformers embedding 模型。"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = get_registry().get("sentence-transformers").create(
            name=settings.lancedb_embedding_model,
        )
    return _embedding_model


def _get_document_schema() -> type[LanceModel]:
    """返回用于「文本 + 向量 + 可选元数据」的 LanceModel  schema（与当前 embedding 维度一致）。"""
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
    """若表不存在则用默认 schema 创建，存在则直接打开。返回表对象。"""
    db = get_db()
    names = db.table_names()
    if table_name in names:
        return db.open_table(table_name)
    schema = _get_document_schema()
    return db.create_table(table_name, schema=schema, exist_ok=True)


def add_documents(
    table_name: str,
    items: list[dict[str, Any]],
) -> int:
    """
    向指定表写入若干条文档。每条需含 "text"，可选 "source"、"extra"。
    自动做向量化并写入，返回写入条数。
    """
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


def search(
    table_name: str,
    query_text: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    在指定表中做语义检索。query_text 会被表关联的 embedding 自动向量化后检索。
    返回列表，每项为包含 text、source、extra 及 _distance 的字典。
    """
    table = ensure_table(table_name)
    results = table.search(query_text).limit(limit).to_list()
    return [dict(r) for r in results]


def list_tables() -> list[str]:
    """列出当前库下所有表名。"""
    return get_db().table_names()
