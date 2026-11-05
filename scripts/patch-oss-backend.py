"""Rebuild a deterministic stored-entry JAR from a pinned base and three OSS entries.

No source compilation or code execution occurs here. Every resulting entry and
the complete JAR must match the locally generated, reviewed delta manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

ALLOWED = {'BOOT-INF/classes/application.yml',
           'BOOT-INF/classes/com/kaoyan/util/OssUtil.class',
           'BOOT-INF/classes/com/kaoyan/config/OssProperties.class'}


def require(condition: object, message: str) -> None:
    """Reject unexpected artifacts without displaying payloads or config values."""
    if not condition:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    """Hash bounded chunks rather than retaining the entire JAR in memory."""
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def build(source: Path, payload: Path, target: Path, report: dict) -> None:
    """Replace only pinned OSS entries and canonicalize ZIP metadata without compression."""
    require(digest(source)==report['baseSha256'],'线上基线JAR哈希不符')
    require(set(report['changed'])==ALLOWED,'只允许三个OSS相关条目')
    require(source.resolve()!=target.resolve(),'禁止覆盖线上基线JAR')
    for name, expected in report['changed'].items():
        require(digest(payload/name)==expected,'增量条目哈希不符')
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED) as output:
        require(set(original.namelist())==set(report['allEntries']),'JAR条目集合不符')
        for name in sorted(original.namelist()):
            data=(payload/name).read_bytes() if name in ALLOWED else original.read(name)
            require(hashlib.sha256(data).hexdigest()==report['allEntries'][name],'JAR内容超出本轮修改')
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.create_system=3
            info.external_attr=((0o40755 if name.endswith('/') else 0o100644)<<16) | (0x10 if name.endswith('/') else 0)
            output.writestr(info,data,compress_type=zipfile.ZIP_STORED)


def main() -> None:
    """Check by default; apply only to a separate staged copy of the pinned baseline."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    require(args.source.resolve()!=args.output.resolve(),'禁止覆盖线上基线JAR')
    report=json.loads(args.manifest.read_text())
    require(digest(args.source)==report['baseSha256'],'基线JAR不符')
    if not args.apply:
        print(json.dumps({'baselineVerified':True,'changes':3}))
        return
    require(not args.output.exists() or digest(args.output)==report['baseSha256'],'暂存JAR已变化')
    temporary=args.output.with_suffix('.oss-staged')
    require(not temporary.exists(),'暂存输出已存在')
    try:
        build(args.source,args.payload,temporary,report)
        require(digest(temporary)==report['targetSha256'],'完整增量JAR哈希不符')
        os.replace(temporary,args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({'baselineVerified':True,'changes':3,'jarSha256':report['targetSha256']}))


if __name__=='__main__':
    main()
