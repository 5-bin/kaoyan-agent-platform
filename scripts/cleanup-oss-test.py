"""Restore this run's test1 NULL avatar and delete its recorded OSS test object."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

import httpx
from dotenv import dotenv_values

from oss_smoke import api, cleanup, require

HELPER_SHA = 'bd0e9bd00ae786b1248c108b7105d65d7802f5e0e5657728eb43189b6a7d76cb'


def main() -> None:
    """Default to receipt checks; require explicit apply for restoration/deletion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--data-helper',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    require(socket.gethostname()=='iZj6cb4euf28b560hanyr7Z' and os.geteuid()==0,'仅限已授权服务器root')
    require(args.receipt.resolve().is_relative_to(Path('/root')) and not args.receipt.is_symlink(),'验收记录边界不符')
    require(args.credentials.stat().st_mode&0o077==0,'凭证文件权限不符')
    receipt = json.loads(args.receipt.read_text())
    require(hashlib.sha256(args.data_helper.read_bytes()).hexdigest()==HELPER_SHA,'数据工具版本不符')
    if not args.apply:
        print(json.dumps({'receiptChecked':True,'applied':False}))
        return
    spec = importlib.util.spec_from_file_location('cleanup_data',args.data_helper)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    v = dotenv_values('/opt/kaoyan/.env')
    require(v.get('DB_HOST','127.0.0.1') in ('localhost','127.0.0.1','::1'),'数据库边界不符')
    db = helper.Database(v['DB_NAME'],['--protocol=SOCKET','--user=root','--default-character-set=utf8mb4'],os.environ.copy())
    credentials = json.loads(args.credentials.read_text())
    with httpx.Client(timeout=20,trust_env=False) as client:
        token = api(client,'POST','/auth/login',body={'username':'test1','password':credentials['test1']})['accessToken']
        try:
            cleanup(client,db,token,receipt)
            args.receipt.write_text(json.dumps(receipt,indent=2))
            print(json.dumps({'originalAvatarRestored':True,'testObjectDeleted':True}))
        finally:
            api(client,'POST','/auth/logout',token)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error,RuntimeError) else '清理失败，异常类别='+type(error).__name__) from None
