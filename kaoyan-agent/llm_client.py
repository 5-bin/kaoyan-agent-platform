"""LLM 客户端（OpenAI 兼容）。"""
import json
import logging
from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def _parse(content: str) -> dict:
    # 去掉 markdown 代码块
    if content.strip().startswith("```"):
        content = content.strip().strip("`").removeprefix("json").strip()
    return json.loads(content)


async def chat(model: str, system: str, user: str) -> dict:
    for attempt in (1, 2):
        try:
            resp = await _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                timeout=30,
            )
            return _parse(resp.choices[0].message.content or "{}")
        except Exception as e:
            logger.warning("LLM call failed attempt=%s err=%s", attempt, e)
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


llm_client = chat
