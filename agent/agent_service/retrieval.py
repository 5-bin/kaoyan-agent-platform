"""检索接口；当前仅关键词工程演示，后续接入中文BM25。"""
from typing import Protocol
from .knowledge import Document
from .schemas import Subject


class Retriever(Protocol):
    def search(self, text: str, limit: int = 3, subject: Subject | None = None) -> list[Document]: ...
