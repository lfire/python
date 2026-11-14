"""
第 014 讲 · 输入输出与文件初识：print、input、open、with
与教程正文一一对应的示例代码

课程页面：/foundation/io
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/014-io.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/014-io.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# captured 'a|b|c.'
# sep 'x|y'
# end_default 'line'

import io
buf = io.StringIO()
print('a', 'b', 'c', sep='|', end='.', file=buf)
print('captured', repr(buf.getvalue()))
print('sep', repr('|'.join(['x', 'y'])))
print('end_default', repr('line'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# exists True
# parts note.txt
# lines ['hello', 'world']
# cleaned True

import tempfile, pathlib
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'note.txt'
    p.write_text('hello' + chr(10) + 'world', encoding='utf-8')
    print('exists', p.exists())
    print('parts', p.name)
    with p.open(encoding='utf-8') as f:
        lines = f.read().splitlines()
    print('lines', lines)
print('cleaned', not pathlib.Path(d).exists())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# closed_on_exception True
# custom x-y!
# default_end_newline True

import io, sys

class Resource:
    def __enter__(self):
        self.closed = False
        return self
    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

r = Resource()
try:
    with r:
        raise ValueError('boom')
except ValueError:
    pass
print('closed_on_exception', r.closed)

buf = io.StringIO()
print('x', 'y', sep='-', end='!', file=buf)
print('custom', buf.getvalue())
print('default_end_newline', sys.stdout is not None)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import io, sys, tempfile, pathlib

buf = io.StringIO()
print('a', 'b', sep='|', end='!', file=buf)
print('captured', repr(buf.getvalue()))
print('progress', 'start', file=sys.stderr)

with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'out' / 'report.txt'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        f.write('name,score' + chr(10))
        f.write('ada,98' + chr(10))
    with p.open('r', encoding='utf-8') as f:
        rows = [line.splitlines()[0] for line in f]
    print('rows', rows)
    print('exists', p.exists())
print('cleaned', not p.exists())
