"""全局依赖：通过 RunContext 注入到各 agent，供工具使用。"""

from dataclasses import dataclass
from typing import Any

from panda_brain.storage import add_documents as _add_documents
from panda_brain.storage import list_tables as _list_tables
from panda_brain.storage import search as _search
from panda_brain.storage import table_has_source as _table_has_source


class LanceDBService:
    """LanceDB 向量库服务：供各 agent 通过 ctx.deps.lancedb 调用。"""

    def add_documents(
        self,
        table_name: str,
        items: list[dict[str, Any]],
    ) -> int:
        """向指定表写入文档列表。每条需含 "text"，可选 "source"、"extra"。返回写入条数。"""
        return _add_documents(table_name, items)

    def search(
        self,
        table_name: str,
        query_text: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """在指定表中做语义检索，返回包含 text、source、extra、_distance 的字典列表。"""
        return _search(table_name, query_text, limit=limit)

    def list_tables(self) -> list[str]:
        """列出当前库下所有表名。"""
        return _list_tables()

    def table_has_source(self, table_name: str, source: str) -> bool:
        """当前库中该表是否已有该 source 的数据。"""
        return _table_has_source(table_name, source)


@dataclass
class Deps:
    """编排器与所有子 agent 共用的依赖。"""

    lancedb: LanceDBService


def create_deps() -> Deps:
    """构造默认 deps 实例（入口处调用一次）。"""
    return Deps(lancedb=LanceDBService())
