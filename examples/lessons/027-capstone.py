"""
第 027 讲 · 阶段综合：词频统计与内存版 KV
与教程正文一一对应的示例代码

课程页面：/containers/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/027-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/027-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# total tokens 10
# hello 2 python 3
# top3 [('python', 3), ('hello', 2), ('313', 1)]
# kv state None 2 1
# bench ran True True

import re, string
from collections import Counter
from time import perf_counter

TRANS = str.maketrans('', '', string.punctuation)

def words(line):
    cleaned = line.casefold().translate(TRANS)
    return re.findall(r'[a-z0-9]+', cleaned)

def count_lines(lines):
    counter = Counter()
    for line in lines:
        counter.update(words(line))
    return counter

TEXT = ['Hello, hello!', 'Python 3.13 and python.', 'Guide to the Python.']
c = count_lines(TEXT)
print('total tokens', c.total())
print('hello', c['hello'], 'python', c['python'])
print('top3', c.most_common(3))

class MemoryKV:
    def __init__(self):
        self._data = {}
    def get(self, key, default=None):
        return self._data.get(key, default)
    def set(self, key, value):
        self._data[key] = value
    def delete(self, key):
        return self._data.pop(key, None) is not None
    def __len__(self):
        return len(self._data)

kv = MemoryKV()
for cmd in [('set', 'a', 1), ('set', 'b', 2), ('delete', 'a')]:
    op = cmd[0]
    if op == 'set':
        kv.set(cmd[1], cmd[2])
    elif op == 'delete':
        kv.delete(cmd[1])
print('kv state', kv.get('a'), kv.get('b'), len(kv))

t0 = perf_counter()
big = count_lines(['w' + str(i) for i in range(2000)])
cost = perf_counter() - t0
print('bench ran', big.total() == 2000, cost >= 0)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# stream count [('a', 3), ('b', 2)]
# shelve keys ['user:1', 'user:2']

import io, shelve, tempfile, os
from collections import Counter

def token_stream(text):
    for line in io.StringIO(text):
        for word in line.split():
            yield word.casefold()

def count_stream(stream):
    c = Counter()
    for token in stream:
        c[token] += 1
    return c

print('stream count', count_stream(token_stream('A a B b a')).most_common())

path = os.path.join(tempfile.gettempdir(), 'depth27.db')
with shelve.open(path) as db:
    db['user:1'] = {'name': 'amy'}
    db['user:2'] = {'name': 'bob'}
    print('shelve keys', sorted(db.keys()))
for suffix in ('', '.db', '.dat', '.dir', '.bak'):
    try:
        os.remove(path + suffix)
    except OSError:
        pass

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# list much larger than gen True
# same counts True
# incremental total 2000 peak positive True

import sys, io, tracemalloc
from collections import Counter

text = 'word ' * 2000
materialized = [w for line in io.StringIO(text) for w in line.split()]
stream = (w for line in io.StringIO(text) for w in line.split())
print('list much larger than gen', sys.getsizeof(materialized) > sys.getsizeof(stream) * 10)
print('same counts', Counter(materialized) == Counter(stream))

tracemalloc.start()
lazy = Counter()
for line in io.StringIO(text):
    for w in line.split():
        lazy[w] += 1
peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print('incremental total', lazy.total(), 'peak positive', peak > 0)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import io, re, string
from collections import Counter

TRANS = str.maketrans('', '', string.punctuation)

def tokenize(lines):
    for line in lines:
        cleaned = line.casefold().translate(TRANS)
        yield from re.findall(r'[a-z0-9]+', cleaned)

def count_stream(lines):
    counter = Counter()
    for token in tokenize(lines):
        counter[token] += 1
    return counter

class MemoryKV:
    def __init__(self): self._data = {}
    def get(self, k, default=None): return self._data.get(k, default)
    def set(self, k, v): self._data[k] = v
    def delete(self, k): return self._data.pop(k, None) is not None

def dispatch(kv, cmd):
    op, k, v = cmd
    if op == 'set': kv.set(k, v)
    elif op == 'delete': kv.delete(k)
    return kv.get(k)

kv = MemoryKV()
doc = io.StringIO('Hello, hello!' + chr(10) + 'Python and python.' + chr(10) + 'Guide to Python.')
counts = count_stream(doc)
dispatch(kv, ('set', 'top', counts.most_common(2)))
dispatch(kv, ('delete', 'missing', None))
print('top', kv.get('top'), 'missing', kv.get('missing'))
print('total', counts.total(), 'hello', counts['hello'], 'python', counts['python'])
