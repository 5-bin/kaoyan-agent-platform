"""首次生成本地.env；不打印凭证、不覆盖现有配置。"""
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / ".env"
    if target.exists():
        print(".env已存在，保留原配置。")
        return
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    content = content.replace("AGENT_INTERNAL_KEY=\n", "AGENT_INTERNAL_KEY=" + secrets.token_hex(24) + "\n")
    content = content.replace("DB_PASSWORD=\n", "DB_PASSWORD=" + secrets.token_hex(24) + "\n")
    with target.open("x", encoding="utf-8") as output:
        output.write(content)
    target.chmod(0o600)
    print("已生成.env，默认离线演示；凭证仅保存在本地文件。")


if __name__ == "__main__":
    main()
