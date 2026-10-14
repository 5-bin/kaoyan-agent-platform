"""只在项目根目录 .env 不存在时生成凭证；不输出凭证，不连接外部服务。"""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
content = (root / '.env.example').read_text(encoding='utf-8')
for name in ('JWT_SECRET', 'AGENT_INTERNAL_KEY'):
    content = content.replace(name + '=\n', name + '=' + secrets.token_hex(32) + '\n')
try:
    fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('.env 已存在，保留原文件。')
else:
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        target.write(content)
    print('已生成 .env，请在本地填写数据库和模型配置；未打印凭证。')
