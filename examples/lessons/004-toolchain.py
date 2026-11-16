"""
第 004 讲 · 工具链全景：写代码、查问题、验质量
与教程正文一一对应的示例代码

课程页面：/guide/toolchain
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/004-toolchain.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/004-toolchain.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# both_positive True
# builtin_faster True
# repeat_len 3

import timeit

setup = 'data = list(range(200))'
loop_stmt = 'total = 0' + chr(10) + 'for x in data: total += x'
builtin_stmt = 'sum(data)'

loop_t = timeit.timeit(loop_stmt, setup=setup, number=2000)
builtin_t = timeit.timeit(builtin_stmt, setup=setup, number=2000)
print('both_positive', loop_t > 0 and builtin_t > 0)
print('builtin_faster', builtin_t < loop_t)
print('repeat_len', len(timeit.repeat(builtin_stmt, setup=setup, number=200, repeat=3)))

# ======================== 2. 对照写法 ========================
# 预期输出：
# warning_level 30
# has_rows True
# has_retry True

import logging, io
stream = io.StringIO()
handler = logging.StreamHandler(stream)
log = logging.getLogger('tool')
log.addHandler(handler)
log.setLevel(logging.INFO)
log.info('rows=%d', 12)
log.warning('retry %s', 'once')
print('warning_level', logging.WARNING)
print('has_rows', 'rows=12' in stream.getvalue())
print('has_retry', 'retry once' in stream.getvalue())

# ======================== 3. 原理验证 ========================
# 预期输出：
# run_module True
# run_path True
# argv_list True
# meta_path_len True
# main_present True

import runpy, sys
main = sys.modules.get('__main__')
print('run_module', callable(getattr(runpy, 'run_module', None)))
print('run_path', callable(getattr(runpy, 'run_path', None)))
print('argv_list', isinstance(sys.argv, list))
print('meta_path_len', len(sys.meta_path) >= 3)
print('main_present', main is not None)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import timeit, logging, io

def bench(stmt, setup, n=2000):
    return min(timeit.repeat(stmt, setup=setup, number=n, repeat=3))

def process(rows, log):
    log.info('rows=%d', len(rows))
    return sum(rows)

def make_log():
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    log = logging.getLogger('pipeline')
    log.handlers = [h]
    log.setLevel(logging.INFO)
    return log, buf

data = list(range(200))
setup = 'data = list(range(200))'
t_loop = bench('total = 0' + chr(10) + 'for x in data: total += x', setup)
t_builtin = bench('sum(data)', setup)
log, buf = make_log()
result = process(data, log)
print('faster', t_builtin < t_loop)
print('result_ok', result == sum(data))
print('logged', 'rows=200' in buf.getvalue())
print('level', logging.INFO)
