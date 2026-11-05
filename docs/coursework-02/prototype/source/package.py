"""Package the current prototype, documentation, sources and acceptance evidence."""
from pathlib import Path
import zipfile

BASE = Path(__file__).resolve().parent.parent
ARCHIVE = BASE / 'T01_T02_墨刀交互原型_v2.zip'
DIRECTORIES = ('html', 'release', 'source', 'screenshots')
files = [p for p in BASE.iterdir() if p.is_file() and p.suffix in ('.md', '.json')]
for name in DIRECTORIES:
    files.extend(p for p in (BASE/name).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
files.sort(key=lambda p: p.relative_to(BASE).as_posix())
with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(file, file.relative_to(BASE))
with zipfile.ZipFile(ARCHIVE) as archive:
    if archive.testzip() is not None:
        raise RuntimeError('Archive integrity check failed')
print(f'Packaged {len(files)} files: {ARCHIVE.name} ({ARCHIVE.stat().st_size} bytes)')
