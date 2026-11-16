"""
第 044 讲 · 鸭子类型、抽象基类与 Protocol
与教程正文一一对应的示例代码

课程页面：/oop/abc
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/044-abc.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/044-abc.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# TypeError abstract
# isinstance True
# protocol isinstance True
# registered True has read: True

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

class Reader(ABC):
    @abstractmethod
    def read(self):
        pass
class FileReader(Reader):
    def read(self):
        return 'file-data'

try:
    Reader()
except TypeError as e:
    print(type(e).__name__, 'abstract')
print('isinstance', isinstance(FileReader(), Reader))

@runtime_checkable
class HasRead(Protocol):
    def read(self) -> str:
        ...
class Duck:
    def read(self):
        return 'duck-data'
print('protocol isinstance', isinstance(Duck(), HasRead))
Reader.register(Duck)
print('registered', isinstance(Duck(), Reader), 'has read:', hasattr(Duck(), 'read'))

# ======================== 2. 对照写法 ========================
# 预期输出：
# registered subclass: True
# has missing method: False
# AttributeError no real method

from abc import ABCMeta

class Meta(metaclass=ABCMeta):
    pass
class NoMethods:
    pass
Meta.register(NoMethods)
print('registered subclass:', issubclass(NoMethods, Meta))
print('has missing method:', hasattr(NoMethods(), 'read'))
try:
    NoMethods().read()
except AttributeError as e:
    print(type(e).__name__, 'no real method')

# ======================== 3. 原理验证 ========================
# 预期输出：
# abstractmethods: frozenset({'read'})
# metaclass: ABCMeta
# isabstract: True
# TypeError needs runtime_checkable
# is_protocol: True

from abc import ABC, abstractmethod
from typing import Protocol
import inspect

class Reader(ABC):
    @abstractmethod
    def read(self):
        pass
print('abstractmethods:', Reader.__abstractmethods__)
print('metaclass:', type(Reader).__name__)
print('isabstract:', inspect.isabstract(Reader))

class PlainProtocol(Protocol):
    def read(self):
        ...
try:
    isinstance(object(), PlainProtocol)
except TypeError:
    print('TypeError needs runtime_checkable')
print('is_protocol:', PlainProtocol._is_protocol)

# ======================== 4. 工程案例 ========================

from typing import Protocol, runtime_checkable

@runtime_checkable
class Exporter(Protocol):
    def export(self, rows):
        ...

class CsvExporter:
    def export(self, rows):
        return ','.join(str(r) for r in rows)
class Broken:
    def run(self):
        return 0

registry = {}
def register(name, obj):
    if not isinstance(obj, Exporter):
        raise TypeError('missing export')
    registry[name] = obj

register('csv', CsvExporter())
try:
    register('bad', Broken())
except TypeError as e:
    print('rejected:', str(e))
print('registered:', sorted(registry))
print('output:', registry['csv'].export([1, 2, 3]))
