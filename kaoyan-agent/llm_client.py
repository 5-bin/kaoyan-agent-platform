"""OpenAI 兼容模型适配；按任务超时，不自动重试付费请求。"""
import json
from datetime import datetime, timezone
from threading import Lock
from openai import AsyncOpenAI
from config import settings


class ModelBudget:
    """单Python实例的模型尝试限额；UTC换日重置，进程重启也会重置。"""
    def __init__(self, today=None):
        self.today = today or (lambda: datetime.now(timezone.utc).date())
        self.day = None
        self.calls = 0
        self.lock = Lock()

    def consume(self, limit):
        with self.lock:
            day = self.today()
            if self.day != day:
                self.day, self.calls = day, 0
            if self.calls >= limit:
                raise RuntimeError("模型每日尝试次数已达上限")
            self.calls += 1


budget = ModelBudget()


def _parse(content: str) -> dict:
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content[3:-3].removeprefix("json").strip()
    value = json.loads(content)
    if not isinstance(value, dict) or not value:
        raise ValueError("模型结果必须是非空JSON对象")
    return value


async def chat(model: str, system: str, user: str) -> dict:
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL.startswith("https://"):
        raise ValueError("模型尚未配置")
    budget.consume(settings.MAX_MODEL_CALLS_PER_DAY)
    async with AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL,
                           max_retries=0, timeout=30) as client:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"}, temperature=0.3,
        )
        return _parse(resp.choices[0].message.content or "{}")


llm_client = chat
