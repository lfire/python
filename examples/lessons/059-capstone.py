"""
第 059 讲 · 阶段综合：简易性能分析器与内存哨兵
与教程正文一一对应的示例代码

课程页面：/core/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/059-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/059-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# top calls 1
# middle calls 1
# leaf calls 2
# top cum > self True

import sys
import time

class MiniProfiler:
    def __init__(self):
        self.stack = []
        self.stats = {}
    def __call__(self, frame, event, arg):
        name = frame.f_code.co_name
        if event == 'call':
            self.stack.append([name, time.perf_counter(), 0.0])
        elif event == 'return' and self.stack:
            key, t0, child = self.stack.pop()
            dt = time.perf_counter() - t0
            rec = self.stats.setdefault(key, [0, 0.0, 0.0])
            rec[0] += 1
            rec[1] += dt - child
            rec[2] += dt
            if self.stack:
                self.stack[-1][2] += dt
        return self

def leaf(n):
    return sum(i * i for i in range(n))

def middle():
    return leaf(2000) + leaf(2000)

def top():
    return middle()

sys.setprofile(MiniProfiler())
top()
prof = sys.getprofile()
sys.setprofile(None)
print('top calls', prof.stats['top'][0])
print('middle calls', prof.stats['middle'][0])
print('leaf calls', prof.stats['leaf'][0])
print('top cum > self', prof.stats['top'][2] > prof.stats['top'][1])

# ======================== 2. 对照写法 ========================
# 预期输出：
# monitoring available True
# saw work True
# event count > 0 True

import sys

events = []
def on_start(code, offset):
    events.append(code.co_name)

def work():
    return sum(i for i in range(50))

if hasattr(sys, 'monitoring'):
    mon = sys.monitoring
    mon.use_tool_id(2, 'sentinel')
    mon.set_events(2, mon.events.PY_START)
    mon.register_callback(2, mon.events.PY_START, on_start)
    work()
    mon.set_events(2, 0)
    mon.register_callback(2, mon.events.PY_START, None)
    mon.free_tool_id(2)
    print('monitoring available', True)
    print('saw work', 'work' in events)
    print('event count > 0', len(events) > 0)
else:
    print('monitoring available', False)

# ======================== 3. 原理验证 ========================
# 预期输出：
# profiled >= plain True
# overhead ratio > 1 True

import sys
import time

def add(a, b):
    return a + b

def busy():
    total = 0
    for i in range(30000):
        total = add(total, i)
    return total

def timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0

plain = min(timed(busy) for _ in range(3))
def nop(frame, event, arg):
    return None
sys.setprofile(nop)
profiled = min(timed(busy) for _ in range(3))
sys.setprofile(None)
print('profiled >= plain', profiled >= plain)
print('overhead ratio > 1', profiled / plain > 1.0)

# ======================== 4. 工程案例 ========================

import io
import pstats
import sys
import time
import tracemalloc

class Sentinel:
    def __init__(self, prefix='', byte_limit=1 << 20):
        self.prefix = prefix
        self.byte_limit = byte_limit
        self.events = 0
        self.base = None
    def __enter__(self):
        tracemalloc.start(1)
        self.base = tracemalloc.take_snapshot()
        sys.setprofile(self._on_event)
        return self
    def _on_event(self, frame, event, arg):
        if event == 'call' and frame.f_code.co_name.startswith(self.prefix):
            self.events += 1
        return self._on_event
    def checkpoint(self):
        now = tracemalloc.take_snapshot()
        diff = now.compare_to(self.base, 'lineno')
        grown = sum(d.size_diff for d in diff if d.size_diff > 0)
        top = sorted(diff, key=lambda d: -d.size_diff)[:3]
        return grown, [d.size_diff for d in top]
    def __exit__(self, *exc):
        sys.setprofile(None)
        grown, top = self.checkpoint()
        print('events', self.events, 'grown', grown, 'alert', grown > self.byte_limit)
        print('top diffs', top, 'peak', tracemalloc.get_traced_memory()[1] > 0)
        tracemalloc.stop()

def hot(n):
    return [dict(i=i) for i in range(n)]

if __name__ == '__main__':
    with Sentinel(prefix='hot', byte_limit=1 << 30) as s:
        hot(3000)
