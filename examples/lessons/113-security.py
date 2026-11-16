"""
第 113 讲 · 安全工程：依赖、注入、序列化与密钥
与教程正文一一对应的示例代码

课程页面：/distributed/security
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/113-security.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/113-security.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# normal [('alice', 'admin')]
# unsafe_rows 2
# safe_rows 0

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE users (name TEXT, role TEXT)')
db.executemany('INSERT INTO users VALUES (?, ?)', [('alice', 'admin'), ('bob', 'user')])

def unsafe(uid):
    q = 'SELECT name, role FROM users WHERE name = ' + chr(39) + uid + chr(39)
    return db.execute(q).fetchall()

def safe(uid):
    q = 'SELECT name, role FROM users WHERE name = ?'
    return db.execute(q, (uid,)).fetchall()

print('normal', safe('alice'))
inj = 'x' + chr(39) + ' OR ' + chr(39) + '1' + chr(39) + '=' + chr(39) + '1'
print('unsafe_rows', len(unsafe(inj)))
print('safe_rows', len(safe(inj)))
db.close()

# ======================== 2. 对照写法 ========================
# 预期输出：
# before []
# out 1
# after ['executed']

import pickle

SIDE_EFFECT = []
def boom():
    SIDE_EFFECT.append('executed')
    return 1

class Payload:
    def __reduce__(self):
        return (boom, ())

blob = pickle.dumps(Payload())
print('before', list(SIDE_EFFECT))
out = pickle.loads(blob)
print('out', out)
print('after', list(SIDE_EFFECT))

# ======================== 3. 原理验证 ========================
# 预期输出：
# token_len 32
# digest_len 64
# redacted abcd****
# hmac_equal True

import hashlib, secrets, hmac

token = secrets.token_hex(16)
digest = hashlib.sha256(token.encode()).hexdigest()
print('token_len', len(token))
print('digest_len', len(digest))
def redact(s):
    return s[:4] + '****' if len(s) > 4 else '****'
print('redacted', redact('abcdefghijk'))
print('hmac_equal', hmac.compare_digest(digest, hashlib.sha256(token.encode()).hexdigest()))

# ======================== 4. 工程案例 ========================

import sqlite3, hashlib, hmac, secrets

class Repo:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE users (name TEXT, role TEXT)')
        self.db.execute('INSERT INTO users VALUES (?, ?)', ('alice', 'admin'))
        self.seen = set()
    def find(self, name):
        cur = self.db.execute('SELECT name, role FROM users WHERE name = ?', (name,))
        return cur.fetchall()
    def redact(self, token):
        return token[:4] + '****' if len(token) > 4 else '****'
    def token(self):
        return secrets.token_hex(16)
    def verify(self, a, b):
        return hmac.compare_digest(a, b)
    def write_once(self, idem, name):
        if idem in self.seen:
            return 'duplicate'
        self.seen.add(idem)
        return 'applied'

r = Repo()
t = r.token()
print('find', r.find('alice'))
print('log_token', r.redact(t))
print('same_token', r.verify(t, t))
print(r.write_once('k1', 'alice'), r.write_once('k1', 'alice'))
