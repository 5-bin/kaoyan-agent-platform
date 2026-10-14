"""启动时一次性加载 prompts/*.txt 到内存。"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
_cache: dict[str, str] = {}


def _load() -> None:
    for f in PROMPTS_DIR.glob("*.txt"):
        _cache[f.stem] = f.read_text(encoding="utf-8")


_load()


def get(name: str) -> str:
    if name not in _cache:
        raise FileNotFoundError(f"prompt not found: {name}")
    return _cache[name]
