"""
第 025 讲 · 迭代协议：iterable、iterator 与惰性求值
与教程正文一一对应的示例代码

课程页面：/containers/iterator
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/025-iterator.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/025-iterator.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# is iterator True True
# first pass [2, 1, 0]
# second pass []
# file is its own iterator True
# list iter gives new True
# read chunks ['ab', 'cd', 'ef']
# islice [10, 11, 12, 13]
# chain [1, 2, 3]
# takewhile [1, 3]
# zip strict ValueError

import io
from collections.abc import Iterator, Iterable
import itertools

class Countdown:
    def __init__(self, n):
        self.n = n
    def __iter__(self):
        return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n

c = Countdown(3)
print('is iterator', isinstance(c, Iterator), isinstance(c, Iterable))
print('first pass', list(c))
print('second pass', list(c))

f = io.StringIO('a' + chr(10) + 'b' + chr(10))
print('file is its own iterator', iter(f) is f)
lst = [1, 2]
print('list iter gives new', iter(lst) is not iter(lst))

def chunks(text, size):
    src = io.StringIO(text)
    return iter(lambda: src.read(size), '')
print('read chunks', list(chunks('abcdef', 2)))

print('islice', list(itertools.islice(itertools.count(10), 4)))
print('chain', list(itertools.chain([1, 2], [3])))
print('takewhile', list(itertools.takewhile(lambda x: x < 4, [1, 3, 5, 2])))
try:
    print(list(zip([1, 2], [3], strict=True)))
except ValueError as e:
    print('zip strict', type(e).__name__)

# ======================== 2. 对照写法 ========================
# 预期输出：
# group a [1, 2]
# group b [3, 4]
# tee independent [1, 2, 3] [1, 2, 3]
# accumulate [1, 3, 6, 10]
# zip_longest [(1, 'a'), (2, '-')]
# bag reusable [1, 2] [1, 2]

import itertools

data = [('a', 1), ('a', 2), ('b', 3), ('b', 4)]
for key, group in itertools.groupby(data, key=lambda r: r[0]):
    print('group', key, [r[1] for r in group])

a, b = itertools.tee([1, 2, 3], 2)
print('tee independent', list(a), list(b))
print('accumulate', list(itertools.accumulate([1, 2, 3, 4])))
print('zip_longest', list(itertools.zip_longest([1, 2], ['a'], fillvalue='-')))

class Bag:
    def __init__(self, items): self.items = list(items)
    def __iter__(self): return iter(self.items)

bag = Bag([1, 2])
print('bag reusable', list(bag), list(bag))

# ======================== 3. 原理验证 ========================
# 预期输出：
# Iterator abstract ['__next__']
# Iterable abstract ['__iter__']
# Iterator isabstract True
# mixin iter Iterator.__iter__
# file is Iterator True
# list_iterator type list_iterator
# first [1, 2] second []
# PEP 479 wraps RuntimeError

import io, inspect
from collections.abc import Iterator, Iterable

print('Iterator abstract', sorted(Iterator.__abstractmethods__))
print('Iterable abstract', sorted(Iterable.__abstractmethods__))
print('Iterator isabstract', inspect.isabstract(Iterator))
print('mixin iter', Iterator.__iter__.__qualname__)

f = io.StringIO('x')
print('file is Iterator', isinstance(f, Iterator))
it = iter([1, 2])
print('list_iterator type', type(it).__name__)
print('first', list(it), 'second', list(it))

def gen():
    yield 1
    raise StopIteration('boom')
try:
    list(gen())
except RuntimeError as e:
    print('PEP 479 wraps', type(e).__name__)

# ======================== 4. 工程案例 ========================

import itertools

PAGES = [
    [101, 102],
    [103, 104],
    [105],
    [],
]

def fetch(page_no):
    return PAGES[page_no] if page_no < len(PAGES) else []

class PagedOrders:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.page = 0
        self.buffer = []
        self.pos = 0
    def __iter__(self):
        return self
    def __next__(self):
        while self.pos >= len(self.buffer):
            rows = self.fetcher(self.page)
            self.page += 1
            if not rows:
                raise StopIteration
            self.buffer = rows
            self.pos = 0
        value = self.buffer[self.pos]
        self.pos += 1
        return value

orders = PagedOrders(fetch)
print('all', list(orders))
print('first three', list(itertools.islice(PagedOrders(fetch), 3)))
print('exhausted again', list(orders))
