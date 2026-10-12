from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    internal_key: str
    mode: str = "demo"
    knowledge_path: Path = Path(__file__).resolve().parents[1] / "knowledge" / "sources.json"
    model_base_url: str = ""
    model_api_key: str = ""
    model_name: str = ""
    model_timeout: float = 30
    max_model_calls_per_day: int = 100

    def validate(self):
        if len(self.internal_key) < 16 or not self.internal_key.isascii():
            raise ValueError("AGENT_INTERNAL_KEY 至少16位ASCII字符，Java/Python需一致")
        if self.mode not in {"demo", "model"}:
            raise ValueError("AGENT_MODE 必须为 demo 或 model")
        if self.mode == "model" and (
            not self.model_base_url.startswith("https://") or not self.model_api_key or not self.model_name
        ):
            raise ValueError("模型模式需要 HTTPS MODEL_BASE_URL、MODEL_API_KEY、MODEL_NAME")
        if not 1 <= self.model_timeout <= 120 or self.max_model_calls_per_day < 1:
            raise ValueError("模型超时或每日限额不合法")

    @classmethod
    def from_env(cls):
        settings = cls(
            internal_key=os.getenv("AGENT_INTERNAL_KEY", ""),
            mode=os.getenv("AGENT_MODE", "demo"),
            knowledge_path=Path(os.getenv("KNOWLEDGE_PATH", str(cls.knowledge_path))),
            model_base_url=os.getenv("MODEL_BASE_URL", ""),
            model_api_key=os.getenv("MODEL_API_KEY", ""),
            model_name=os.getenv("MODEL_NAME", ""),
            model_timeout=float(os.getenv("MODEL_TIMEOUT_SECONDS", "30")),
            max_model_calls_per_day=int(os.getenv("MAX_MODEL_CALLS_PER_DAY", "100")),
        )
        settings.validate()
        return settings
