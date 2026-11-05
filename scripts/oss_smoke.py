"""Exercise only this run's test1 avatar, then restore and remove that object."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import httpx

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5Z8AAAAASUVORK5CYII=')


def require(condition: object, message: str) -> None:
    """Reject unexpected test identities, resources and response states."""
    if not condition:
        raise RuntimeError(message)


def api(client: httpx.Client, method: str, path: str, token: str = '', body: object = None,
        status: int = 200, **kwargs: object) -> object:
    """Use the local Java API without logging passwords, tokens or raw errors."""
    response = client.request(method,'http://127.0.0.1:8080/api'+path,
                              headers={'Authorization':'Bearer '+token} if token else {},
                              json=body,**kwargs)
    require(response.status_code == status,'头像验收HTTP状态不符: '+path+' '+str(response.status_code))
    value = response.json()
    if status == 200:
        require(value.get('code') == 0,'头像验收业务失败')
    return value.get('data')


def cleanup(client: httpx.Client, db: object, token: str, receipt: dict) -> None:
    """Restore NULL only if test1 still owns the recorded test URL, then delete it."""
    me = api(client,'GET','/users/me',token)
    owner = int(receipt['ownerId'])
    key = receipt['objectKey']
    url = receipt['url']
    require(me['username']=='test1' and int(me['id'])==owner,'清理账号不符')
    require(re.fullmatch(r'prod/avatar/'+str(owner)+r'/[0-9]{8}/[a-zA-Z0-9-]+\.(png|jpg|jpeg|gif|webp)',key),'清理对象不符')
    require(url.endswith('/'+key) and not urlsplit(url).query,'清理URL不符')
    require(me.get('avatarUrl') in (None,'',url),'头像已被其他操作改变，停止恢复')
    if me.get('avatarUrl') == url:
        encoded = 'CONVERT(0x'+url.encode().hex()+' USING utf8mb4)'
        db.query(f"START TRANSACTION; SELECT id FROM user WHERE id={owner} AND username='test1' FOR UPDATE; UPDATE user SET avatar_url=NULL WHERE id={owner} AND username='test1' AND avatar_url={encoded}; COMMIT;")
    require(api(client,'GET','/users/me',token).get('avatarUrl') in (None,''),'原头像恢复失败')
    api(client,'DELETE','/files',token,params={'objectKey':key})
    receipt['originalAvatarRestored'] = True
    receipt['testObjectDeleted'] = True


def exercise(db: object, credentials: Path, output: Path, oss_config: Path) -> None:
    """Check upload/read/ownership/privacy in maintenance, with bounded cleanup."""
    passwords = json.loads(credentials.read_text())
    config = json.loads(oss_config.read_text())
    expected_host = config['OSS_BUCKET_NAME']+'.'+urlsplit(config['OSS_ENDPOINT']).hostname
    tokens: list[str] = []
    receipt = None
    with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
        try:
            first = api(client,'POST','/auth/login',body={'username':'test1','password':passwords['test1']})['accessToken']
            tokens.append(first)
            second = api(client,'POST','/auth/login',body={'username':'test2','password':passwords['test2']})['accessToken']
            tokens.append(second)
            me = api(client,'GET','/users/me',first)
            require(me['username']=='test1' and me.get('avatarUrl') in (None,''),'验收账号已有头像')
            owner = int(me['id'])
            response = api(client,'POST','/files/upload',first,files={'file':('probe.png',PNG,'image/png')},data={'module':'avatar'})
            receipt = {'ownerId':owner,'objectKey':response['objectKey'],'url':response['url']}
            (output/'oss-smoke.json').write_text(json.dumps(receipt))
            require(re.fullmatch(r'prod/avatar/'+str(owner)+r'/[0-9]{8}/[a-z0-9]+\.png',receipt['objectKey']),'上传对象目录不符')
            parsed = urlsplit(receipt['url'])
            require(parsed.scheme=='https' and parsed.hostname==expected_host and parsed.path=='/'+receipt['objectKey'] and not parsed.query,'上传URL不符')
            api(client,'PUT','/users/avatar',first,{'avatarUrl':receipt['url']})
            content = client.get('http://127.0.0.1:8080/api/users/avatar/content',headers={'Authorization':'Bearer '+first})
            require(content.status_code==200 and content.content==PNG,'认证头像字节不符')
            require(client.get(receipt['url']).status_code==403,'匿名对象访问未拒绝')
            require(client.get('http://127.0.0.1:8080/api/users/avatar/content').status_code==401,'未认证头像访问未拒绝')
            api(client,'PUT','/users/avatar',second,{'avatarUrl':receipt['url']},status=400)
            api(client,'DELETE','/files',second,status=404,params={'objectKey':receipt['objectKey']})
            api(client,'DELETE','/files',first,status=409,params={'objectKey':receipt['objectKey']})
            require(api(client,'GET','/auth/config')=={'registrationEnabled':False},'注册状态改变')
            receipt.update(uploadVerified=True,authenticatedBytesMatch=True,anonymousObject403=True,unauthenticatedAvatar401=True,crossAccountBind400=True,crossAccountDelete404=True,currentAvatarDelete409=True)
        finally:
            try:
                if receipt is not None:
                    cleanup(client,db,tokens[0],receipt)
                    (output/'oss-smoke.json').write_text(json.dumps(receipt,indent=2))
            finally:
                for token in tokens:
                    api(client,'POST','/auth/logout',token)
