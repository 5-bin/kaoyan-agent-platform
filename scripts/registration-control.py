"""Temporarily guard public registration and close the server-owned backend flag."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

import httpx
from dotenv import dotenv_values

SITE = Path('/etc/nginx/sites-available/kaoyan')
ENV = Path('/opt/kaoyan/.env')
BLOCK = '''    # BEGIN kaoyan-test-registration-guard
    location = /api/auth/register {
        default_type application/json;
        return 403 '{"code":403,"message":"当前暂不开放注册","data":null}';
    }
    location = /api/auth/register/ {
        default_type application/json;
        return 403 '{"code":403,"message":"当前暂不开放注册","data":null}';
    }
    # END kaoyan-test-registration-guard
'''


def require(condition: object, message: str) -> None:
    """Reject an unexpected config transition without displaying private config."""
    if not condition:
        raise RuntimeError(message)


def render_guard(text: str, enable: bool) -> str:
    """Change only this tool's complete marked block at the known API location."""
    if BLOCK in text:
        require(text.count(BLOCK) == 1, '重复注册拦截块')
        return text if enable else text.replace(BLOCK, '', 1)
    require('kaoyan-test-registration-guard' not in text, '注册拦截块不完整')
    require(enable, '没有本工具创建的注册拦截块')
    require(text.count('    location /api/ {') == 1, 'API布局不符')
    return text.replace('    location /api/ {', BLOCK + '    location /api/ {', 1)


def close_flag(text: str) -> str:
    """Set the single registration flag while preserving every other config line."""
    pattern = r'(?m)^(?:export\s+)?REGISTRATION_ENABLED=.*$'
    matches = re.findall(pattern, text)
    require(len(matches) <= 1, '注册配置重复')
    return re.sub(pattern, 'REGISTRATION_ENABLED=false', text) if matches else text.rstrip('\n') + '\nREGISTRATION_ENABLED=false\n'


def write(path: Path, content: bytes, stat: os.stat_result) -> None:
    """Atomically write a known config, preserving its exact mode and ownership."""
    fd, name = tempfile.mkstemp(prefix='.registration-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.st_mode & 0o777)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def nginx_check() -> None:
    """Validate and reload Nginx, hiding arbitrary raw configuration diagnostics."""
    for command in (['nginx', '-t'], ['systemctl', 'reload', 'nginx']):
        result = subprocess.run(command, capture_output=True, timeout=20)
        require(result.returncode == 0, 'Nginx检查或重载失败')


def main() -> None:
    """Preview by default; retain original config backups for authorized changes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('status', 'guard', 'close-backend', 'unguard'), default='status')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    require(socket.gethostname() == 'iZj6cb4euf28b560hanyr7Z' and os.geteuid() == 0, '仅限已授权服务器root')
    require(args.output.parent == Path('/root') and not args.output.is_symlink(), '输出目录边界不符')
    original = SITE.read_bytes()
    env = ENV.read_bytes()
    if not args.apply or args.action == 'status':
        print(json.dumps({'publicGuarded': BLOCK in original.decode(), 'registrationConfigured': dotenv_values(ENV).get('REGISTRATION_ENABLED', '<default true>')}))
        return
    os.umask(0o077)
    args.output.mkdir(mode=0o700, exist_ok=True)
    require(args.output.stat().st_mode & 0o077 == 0, '输出目录不私密')
    for path, content in ((SITE, original), (ENV, env)):
        backup = args.output / (path.name + '.before')
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write(content)
    if args.action == 'close-backend':
        require(BLOCK in original.decode(), '先保护公网注册再关闭后端配置')
        require(ENV.read_bytes() == env, '环境配置被并发修改')
        write(ENV, close_flag(env.decode()).encode(), ENV.stat())
    else:
        if args.action == 'unguard':
            require(dotenv_values(ENV).get('REGISTRATION_ENABLED') == 'false', '后端配置未关闭注册')
            with httpx.Client(trust_env=False, timeout=10) as client:
                response = client.get('http://127.0.0.1:8080/api/auth/config')
                require(response.status_code == 200 and response.json().get('data') == {'registrationEnabled': False}, '运行后端未关闭注册')
        candidate = render_guard(original.decode(), args.action == 'guard').encode()
        require(SITE.read_bytes() == original, 'Nginx被并发修改')
        stat = SITE.stat()
        try:
            write(SITE, candidate, stat)
            nginx_check()
        except Exception:
            write(SITE, original, stat)
            nginx_check()
            raise
    print(json.dumps({'action': args.action, 'applied': True}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else '配置未完成，异常类别=' + type(error).__name__) from None
