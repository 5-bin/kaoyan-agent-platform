"""离线核对仓库文档与配置，不访问模型或改写文件。"""
from pathlib import Path
import json
import re
from urllib.parse import unquote
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", ".cache", "target", "__pycache__", ".pytest_cache", "node_modules", "验证输出"}


def files():
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part in EXCLUDED for part in p.relative_to(ROOT).parts)]


def main():
    errors = []
    counts = {"documents": 0, "fileLinks": 0, "anchors": 0, "jsonExamples": 0, "tables": 0}
    for p in files():
        if p.suffix != ".md":
            continue
        counts["documents"] += 1
        source = p.read_text(encoding="utf-8")
        if len(re.findall(r"^```", source, re.M)) % 2:
            errors.append(str(p.relative_to(ROOT)) + ": code fences")
        for block in re.findall(r"^```json\s*\n(.*?)^```", source, re.S | re.M):
            json.loads(block); counts["jsonExamples"] += 1
        text = re.sub(r"^```.*?^```\s*$", "", source, flags=re.S | re.M)
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if link.startswith(("http://", "https://")):
                continue
            path, _, anchor = link.partition("#")
            target = (p.parent / unquote(path)).resolve() if path else p
            if not target.is_relative_to(ROOT):
                errors.append(f"link outside repository: {link}"); continue
            if path:
                counts["fileLinks"] += 1
                if not target.is_file():
                    errors.append(f"missing file: {link}"); continue
            if anchor:
                counts["anchors"] += 1
                if f'id="{anchor}"' not in target.read_text(encoding="utf-8"):
                    errors.append(f"missing anchor: {link}")
        width = None
        for line in text.splitlines():
            if line.startswith("|") and line.endswith("|"):
                current = len(line.split("|")) - 2
                if width is None:
                    counts["tables"] += 1; width = current
                elif width != current:
                    errors.append(f"table columns: {p.name}")
            else:
                width = None
    for p in files():
        if p.suffix == ".json":
            json.loads(p.read_text(encoding="utf-8"))
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert "ports" not in compose["services"]["agent"]
    assert "ports" not in compose["services"]["database"]
    assert compose["services"]["backend"]["ports"] == ["127.0.0.1:8080:8080"]
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}
    design = (ROOT / "考研Agent平台搭建文档.md").read_text(encoding="utf-8")
    assert re.findall(r"^## (\d+)\.", design, re.M) == [str(i) for i in range(1, 11)]
    assert not errors, errors
    print(json.dumps({"checks": counts, "result": "passed", "configScope": "static YAML only"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
