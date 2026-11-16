"""
第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制
与教程正文一一对应的示例代码

课程页面：/projects/kv-wal
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/131-kv-wal.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/131-kv-wal.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# replay ({'b': '2'}, 3, 0)
# crash replay ({'a': '1', 'b': '2'}, 2, 1)
# checkpoint ['a', 'b']
# wal empty True
# snap {'a': '1', 'b': '2'}

import json, os, struct, tempfile, zlib

def encode_rec(rec):
    body = json.dumps(rec, sort_keys=True).encode()
    return struct.pack('>II', len(body), zlib.crc32(body) & 0xffffffff) + body

def append(path, rec, fsync=False):
    with open(path, 'ab') as f:
        f.write(encode_rec(rec))
        f.flush()
        if fsync:
            os.fsync(f.fileno())

def replay(path):
    state, valid, corrupt = {}, 0, 0
    data = open(path, 'rb').read()
    pos = 0
    while pos + 8 <= len(data):
        length, crc = struct.unpack('>II', data[pos:pos + 8])
        end = pos + 8 + length
        if end > len(data) or (zlib.crc32(data[pos + 8:end]) & 0xffffffff) != crc:
            corrupt += 1
            break
        rec = json.loads(data[pos + 8:end])
        if rec['op'] == 'DEL':
            state.pop(rec['key'], None)
        else:
            state[rec['key']] = rec['value']
        valid += 1
        pos = end
    return state, valid, corrupt

def checkpoint(path, snap):
    state, _, _ = replay(path)
    with open(snap, 'w', encoding='utf-8') as f:
        json.dump(state, f, sort_keys=True)
    open(path, 'wb').close()
    return sorted(state)

work = tempfile.mkdtemp()
wal = os.path.join(work, 'kv.wal')
append(wal, {'op': 'SET', 'key': 'a', 'value': '1'}, fsync=True)
append(wal, {'op': 'SET', 'key': 'b', 'value': '2'})
append(wal, {'op': 'DEL', 'key': 'a', 'value': ''})
print('replay', replay(wal))
raw = open(wal, 'rb').read()
open(wal, 'wb').write(raw[:-3])
print('crash replay', replay(wal))
snap = os.path.join(work, 'snap.json')
print('checkpoint', checkpoint(wal, snap))
print('wal empty', os.path.getsize(wal) == 0)
print('snap', json.load(open(snap, encoding='utf-8')))

# ======================== 2. 对照写法 ========================
# 预期输出：
# memory-first ('ack', None)
# wal-first ('ack', '1')

def simulate(order):
    mem, disk = {}, []
    def write(k, v):
        if order == 'memory-first':
            mem[k] = v
            return 'ack'
        disk.append((k, v))
        mem[k] = v
        return 'ack'
    ack = write('a', '1')
    return ack, dict(disk).get('a')

print('memory-first', simulate('memory-first'))
print('wal-first', simulate('wal-first'))

# ======================== 3. 原理验证 ========================
# 预期输出：
# sizes 5 8 3
# header bytes 8
# fsync signature (fd)

import os, struct, tempfile, inspect

p = os.path.join(tempfile.mkdtemp(), 'w')
with open(p, 'ab') as f:
    f.write(b'12345')
    f.flush()
    os.fsync(f.fileno())
s1 = os.stat(p).st_size
with open(p, 'ab') as f:
    f.write(b'678')
s2 = os.stat(p).st_size
print('sizes', s1, s2, s2 - s1)
print('header bytes', struct.calcsize('>II'))
print('fsync signature', str(inspect.signature(os.fsync)))

# ======================== 4. 工程案例 ========================

import json, os, struct, tempfile, threading, zlib

class KV:
    def __init__(self, path, fsync_policy='always', shards=4):
        self.path = path
        self.policy = fsync_policy
        self.locks = [threading.Lock() for _ in range(shards)]
        self.data = {}
        self._replay()
    def _rec(self, op, key, value):
        body = json.dumps({'op': op, 'key': key, 'value': value}, sort_keys=True).encode()
        return struct.pack('>II', len(body), zlib.crc32(body) & 0xffffffff) + body
    def _append(self, rec):
        with open(self.path, 'ab') as f:
            f.write(rec)
            f.flush()
            if self.policy == 'always':
                os.fsync(f.fileno())
    def _replay(self):
        data = open(self.path, 'rb').read() if os.path.exists(self.path) else b''
        pos = 0
        while pos + 8 <= len(data):
            n, crc = struct.unpack('>II', data[pos:pos + 8])
            end = pos + 8 + n
            if end > len(data) or (zlib.crc32(data[pos + 8:end]) & 0xffffffff) != crc:
                break
            r = json.loads(data[pos + 8:end])
            self.data[r['key']] = r['value']
            pos = end
    def set(self, key, value):
        idx = hash(key) % len(self.locks)
        with self.locks[idx]:
            self._append(self._rec('SET', key, value))
            self.data[key] = value
    def get(self, key):
        return self.data.get(key)

p = os.path.join(tempfile.mkdtemp(), 'kv.wal')
kv = KV(p)
kv.set('a', '1')
kv.set('b', '2')
print('before', kv.get('a'), kv.get('b'))
print('reopen', KV(p).get('a'), KV(p).get('b'))
print('shards', len(kv.locks), 'policy', kv.policy)
