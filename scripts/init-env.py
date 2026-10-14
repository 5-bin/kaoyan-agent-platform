"""Create a shared root .env without overwriting existing configuration or printing secrets."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env 已存在，保留现有配置。")
else:
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace("AGENT_INTERNAL_KEY=\n", "AGENT_INTERNAL_KEY=" + secrets.token_urlsafe(32) + "\n")
    template = template.replace("JWT_SECRET=\n", "JWT_SECRET=" + secrets.token_urlsafe(48) + "\n")
    with target.open("x", encoding="utf-8", newline="\n") as output:
        output.write(template)
    print("已生成根目录 .env；请填写本地数据库账号，凭证未输出。")
