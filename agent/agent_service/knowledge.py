import json
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .schemas import Source, Subject


class Document(Source):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(min_length=1)
    content: str = Field(min_length=1)
    origin: str
    retrievedAt: str
    license: str
    subject: Subject
    reviewStatus: str = "demo_unreviewed"

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value.startswith("/references/") and ".." not in value and "\\" not in value:
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username:
            raise ValueError("来源链接仅允许 /references/ 本地路径或 HTTPS 地址")
        return value

    def source(self):
        return Source(**self.model_dump(include=set(Source.model_fields)))


class KnowledgeBase:
    def __init__(self, path: Path):
        self.documents = [Document.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        ids = [doc.id for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("资料编号重复")

    def search(self, text: str, limit: int = 3, subject: Subject | None = None):
        query = text.lower()
        ranked = [(sum(word.lower() in query for word in doc.keywords), doc) for doc in self.documents if subject is None or doc.subject == subject]
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [doc for score, doc in ranked if score > 0][:limit]
