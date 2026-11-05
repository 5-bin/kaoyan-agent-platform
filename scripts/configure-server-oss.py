"""Configure this authorized server's OSS settings, with exact guarded rollback."""
from __future__ import annotations

import argparse
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit

from dotenv import dotenv_values

ENV = Path('/opt/kaoyan/.env')
KEYS = {'OSS_ENDPOINT','OSS_BUCKET_NAME','OSS_ACCESS_KEY_ID','OSS_ACCESS_KEY_SECRET','OSS_URL_PREFIX','OSS_KEY_PREFIX'}


def require(condition: object, message: str) -> None:
    """Reject unsafe state changes without showing any config values."""
    if not condition:
        raise RuntimeError(message)


def merge(original: str, values: dict[str, str]) -> str:
    """Replace only OSS lines, preserving all unrelated environment values."""
    require(set(values) == KEYS and all(isinstance(v,str) and '\n' not in v and '\r' not in v for v in values.values()), 'OSS配置字段不符')
    endpoint = urlsplit(values['OSS_ENDPOINT'])
    require(endpoint.scheme == 'https' and endpoint.hostname and endpoint.hostname.endswith('.aliyuncs.com') and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment and endpoint.path in ('','/'), 'OSS端点不符')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]',values['OSS_BUCKET_NAME']), 'Bucket名称不符')
    require(values['OSS_ACCESS_KEY_ID'] and values['OSS_ACCESS_KEY_SECRET'] and values['OSS_URL_PREFIX']=='' and values['OSS_KEY_PREFIX']=='prod/', 'OSS配置不完整或目录不符')
    before = dotenv_values(stream=StringIO(original))
    result = original
    for key, value in sorted(values.items()):
        pattern = r'(?m)^(?:export\s+)?' + key + r'=.*$'
        require(len(re.findall(pattern,result)) <= 1, 'OSS配置重复')
        replacement = key + '=' + json.dumps(value,ensure_ascii=True)
        result = re.sub(pattern,lambda _:replacement,result) if re.search(pattern,result) else result.rstrip('\n')+'\n'+replacement+'\n'
    after = dotenv_values(stream=StringIO(result))
    require(all(after[k] == v for k,v in values.items()), '配置转义核验失败')
    require({k:v for k,v in before.items() if k not in KEYS} == {k:v for k,v in after.items() if k not in KEYS}, '其他环境配置发生变化')
    return result


def write(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
    """Atomically replace a reviewed config while retaining ownership and mode."""
    fd,name = tempfile.mkstemp(prefix='.oss-config-',dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.chown(temporary,uid,gid)
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def avatars(values: dict) -> int:
    """Check only the count of existing avatars through the local DB socket."""
    require(values.get('DB_HOST','127.0.0.1') in ('127.0.0.1','localhost','::1'), '数据库边界不符')
    result = subprocess.run(['mysql','--no-defaults','--protocol=SOCKET','--user=root','--batch','--skip-column-names',values['DB_NAME']],input="SELECT COUNT(*) FROM user WHERE avatar_url IS NOT NULL AND avatar_url<>'';",text=True,capture_output=True,timeout=15)
    require(result.returncode==0,'头像数量核对失败')
    return int(result.stdout.strip())


def main() -> None:
    """Default to read-only checks; persist private preimages before explicit apply."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    require(socket.gethostname()=='iZj6cb4euf28b560hanyr7Z' and os.geteuid()==0,'仅限已授权服务器root')
    require(args.output.parent==Path('/root') and not args.output.is_symlink(),'输出目录边界不符')
    original = ENV.read_bytes()
    if args.restore:
        report = json.loads((args.output/'config-result.json').read_text())
        current_sha = hashlib.sha256(original).hexdigest()
        require(current_sha in (report['appliedSha256'], report['beforeSha256']),'配置在应用后改变，禁止覆盖')
        backup = (args.output/'env.before').read_bytes()
        require(hashlib.sha256(backup).hexdigest()==report['beforeSha256'],'备份哈希不符')
        if args.apply:
            write(ENV,backup,report['mode'],report['uid'],report['gid'])
        print(json.dumps({'restored':args.apply}))
        return
    require(args.config and args.config.is_file() and not args.config.is_symlink() and args.config.stat().st_mode&0o077==0,'需要私密配置文件')
    values = json.loads(args.config.read_text())
    candidate = merge(original.decode(),values).encode()
    current = dotenv_values(ENV)
    require(all(not current.get(key) for key in KEYS),'服务器已有OSS配置，停止覆盖')
    require(avatars(current)==0,'已有头像，需先核对兼容')
    require(current.get('LLM_ENABLED')=='false' and current.get('REGISTRATION_ENABLED')=='false','模型或注册状态不符')
    if not args.apply:
        print(json.dumps({'checked':True,'existingAvatars':0,'credentialsPrinted':False}))
        return
    require(not args.output.exists(),'需要新的备份目录')
    os.umask(0o077)
    args.output.mkdir(mode=0o700)
    stat = ENV.stat()
    (args.output/'env.before').write_bytes(original)
    require(ENV.read_bytes()==original,'环境配置被并发修改')
    report = {'beforeSha256':hashlib.sha256(original).hexdigest(),'appliedSha256':hashlib.sha256(candidate).hexdigest(),'mode':stat.st_mode&0o777,'uid':stat.st_uid,'gid':stat.st_gid}
    (args.output/'config-result.json').write_text(json.dumps(report,indent=2))
    write(ENV,candidate,report['mode'],report['uid'],report['gid'])
    print(json.dumps({'applied':True,'namespace':'prod/','otherConfigPreserved':True}))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error,RuntimeError) else '配置失败，异常类别='+type(error).__name__) from None
