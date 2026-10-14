"""Read-only checks for current (not historical prompt) docs, JSON, Python, and CI paths."""
import ast
import json
import re
from pathlib import Path
from urllib.parse import unquote
import yaml

root = Path(__file__).resolve().parents[1]
documents = [root / p for p in ("README.md", "AGENTS.md", "docs/rag.md", "docs/validation-rag.md")]
for doc in documents:
    text = doc.read_text(encoding="utf-8")
    for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if "://" in link or link.startswith("#"):
            continue
        target = (doc.parent / unquote(link.split("#", 1)[0])).resolve()
        if not target.exists():
            raise SystemExit(f"Broken link: {doc.name}: {link}")
for path in (root / "kaoyan-agent").rglob("*.py"):
    if not any(part in {".venv", "__pycache__", ".cache"} for part in path.parts):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
json.loads((root / "kaoyan-agent/knowledge/corpus.json").read_text(encoding="utf-8"))
workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
for step in workflow["jobs"]["verify"]["steps"]:
    for relative in str(step.get("with", {}).get("cache-dependency-path", "")).splitlines():
        if relative and not (root / relative).is_file():
            raise SystemExit(f"Missing CI dependency: {relative}")
print("Current docs, JSON, Python syntax and CI dependency paths passed.")
