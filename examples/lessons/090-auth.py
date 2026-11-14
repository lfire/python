"""
第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC
与教程正文一一对应的示例代码

课程页面：/server/auth
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/090-auth.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/090-auth.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# parts 3
# header b64 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
# verify valid sub=u42
# tampered bad signature
# expired expired

import hmac, hashlib, base64, json, time
def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
SECRET = b'dev-secret'
def sign(header, payload):
    h = b64url(json.dumps(header, separators=(',',':')).encode())
    p = b64url(json.dumps(payload, separators=(',',':')).encode())
    sig = b64url(hmac.new(SECRET, (h + '.' + p).encode(), hashlib.sha256).digest())
    return h + '.' + p + '.' + sig
def verify(token):
    try:
        h, p, s = token.split('.')
        expect = b64url(hmac.new(SECRET, (h + '.' + p).encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(s, expect):
            return 'bad signature'
        payload = json.loads(base64.urlsafe_b64decode(p + '==='))
        if payload.get('exp', 0) < time.time():
            return 'expired'
        return 'valid sub=' + str(payload.get('sub'))
    except Exception as e:
        return 'invalid ' + type(e).__name__
tok = sign({'alg':'HS256','typ':'JWT'}, {'sub':'u42','exp': time.time() + 60})
print('parts', len(tok.split('.')))
print('header b64', tok.split('.')[0])
print('verify', verify(tok))
print('tampered', verify(tok[:-2] + 'xx'))
old = sign({'alg':'HS256','typ':'JWT'}, {'sub':'u42','exp': time.time() - 1})
print('expired', verify(old))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# salt bytes 16
# digest bytes 32
# verify True
# wrong False

import hashlib, os, hmac

def hash_password(pw, salt=None):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, 200000)
    return salt.hex(), dk.hex()

s, h = hash_password('s3cret')
s2, h2 = hash_password('s3cret', bytes.fromhex(s))
print('salt bytes', len(bytes.fromhex(s)))
print('digest bytes', len(bytes.fromhex(h)))
print('verify', hmac.compare_digest(h, h2))
print('wrong', hmac.compare_digest(h, hash_password('wrong', bytes.fromhex(s))[1]))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# method S256
# challenge E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
# plain != hashed True

import hashlib, base64

verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
print('method S256')
print('challenge', challenge)
print('plain != hashed', verifier != challenge)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import hmac, hashlib, base64, json, time

SECRET = b'k1'
revoked = set()
audit = []
ROLES = {'admin': {'read', 'write', 'delete'}, 'viewer': {'read'}}

def b64(d):
    return base64.urlsafe_b64encode(d).rstrip(b'=').decode()

def issue(sub, roles):
    h = b64(json.dumps({'alg':'HS256','kid':'k1'}, separators=(',',':')).encode())
    p = b64(json.dumps({'sub':sub, 'roles':roles, 'exp':time.time()+900}, separators=(',',':')).encode())
    s = b64(hmac.new(SECRET, (h+'.'+p).encode(), hashlib.sha256).digest())
    return h+'.'+p+'.'+s

def verify(tok):
    h, p, s = tok.split('.')
    exp_sig = b64(hmac.new(SECRET, (h+'.'+p).encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(s, exp_sig):
        return None
    payload = json.loads(base64.urlsafe_b64decode(p+'==='))
    if payload['exp'] < time.time() or payload['sub'] in revoked:
        return None
    return payload

def authorize(tok, action, resource):
    p = verify(tok)
    ok = p is not None and action in set().union(*(ROLES.get(r,set()) for r in p['roles']))
    audit.append((p['sub'] if p else '?', action, resource, ok))
    return ok

admin = issue('u1', ['admin'])
viewer = issue('u2', ['viewer'])
print(authorize(admin, 'delete', 'order/9'))
print(authorize(viewer, 'delete', 'order/9'))
revoked.add('u1')
print(authorize(admin, 'read', 'order/9'))
print('audit rows', len(audit))
