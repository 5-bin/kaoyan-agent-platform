"""环境初始化的回归验证，始终使用独立临时目录。"""
from pathlib import Path
import shutil
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[2]


def prepare(tmp_path):
    (tmp_path / 'scripts').mkdir()
    shutil.copyfile(ROOT / 'scripts/init-env.py', tmp_path / 'scripts/init-env.py')
    shutil.copyfile(ROOT / '.env.example', tmp_path / '.env.example')
    return [sys.executable, '-X', 'utf8', str(tmp_path / 'scripts/init-env.py')]


def test_init_env_generates_private_distinct_keys_without_printing_them(tmp_path):
    result = subprocess.run(prepare(tmp_path), check=True, text=True, encoding='utf-8', capture_output=True)
    content = (tmp_path / '.env').read_text()
    values = dict(line.split('=', 1) for line in content.splitlines() if '=' in line and not line.startswith('#'))
    assert len(values['JWT_SECRET']) == 64
    assert len(values['AGENT_INTERNAL_KEY']) == 64
    assert values['JWT_SECRET'] != values['AGENT_INTERNAL_KEY']
    assert values['JWT_SECRET'] not in result.stdout + result.stderr
    assert values['AGENT_INTERNAL_KEY'] not in result.stdout + result.stderr
    if os.name != 'nt':
        assert (tmp_path / '.env').stat().st_mode & 0o777 == 0o600


def test_init_env_preserves_existing_configuration(tmp_path):
    command = prepare(tmp_path)
    existing = tmp_path / '.env'
    existing.write_text('task-owned-test-configuration\n')
    before = existing.stat().st_mtime_ns
    subprocess.run(command, check=True, capture_output=True)
    assert existing.read_text() == 'task-owned-test-configuration\n'
    assert existing.stat().st_mtime_ns == before
