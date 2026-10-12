"""资料版本边界；不是管理员审核发布流程。"""
from pathlib import Path
from typing import Protocol
from .knowledge import KnowledgeBase

DEMO_RELEASE = "demo-408-v1"


class ReleaseProvider(Protocol):
    def load(self, release_id: str) -> KnowledgeBase: ...


class DemoReleaseProvider:
    def __init__(self, path: Path):
        self.knowledge = KnowledgeBase(path)

    def load(self, release_id: str) -> KnowledgeBase:
        if release_id != DEMO_RELEASE:
            raise ValueError("未提供正式资料版本")
        return self.knowledge
