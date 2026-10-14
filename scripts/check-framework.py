"""核对当前目录/启动契约；不能替代真实数据库、模型或浏览器验收。"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
for path in (
    'kaoyan-B/mvnw', 'kaoyan-B/mvnw.cmd', 'kaoyan-B/.mvn/wrapper/maven-wrapper.properties',
    'kaoyan-B/src/main/resources/application-dev.example.yml',
    'kaoyan-agent/main.py', 'kaoyan-agent/requirements-dev.txt', '.env.example',
    'docs/当前框架适配.md',
):
    assert (root / path).is_file(), path
ET.parse(root / 'kaoyan-B/pom.xml')
package = json.loads((root / 'kaoyan-frontend/package.json').read_text())
assert 'build' in package['scripts']
workflow = (root / '.github/workflows/ci.yml').read_text()
for path in ('kaoyan-B', 'kaoyan-agent', 'kaoyan-frontend'):
    assert path in workflow
assert 'scripts/smoke.py' not in workflow
assert 'working-directory: backend' not in workflow
print('当前框架入口与CI路径检查通过；运行与外部服务需另行验收。')
