"""
第 048 讲 · 阶段综合：最小 ORM 与校验框架
与教程正文一一对应的示例代码

课程页面：/oop/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/048-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/048-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# fields ['name', 'uid']
# values 1 ann
# rejected uid needs int

class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError(self.name + ' needs ' + self.typ.__name__)
        obj._data[self.name] = value

class Meta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls._fields = tuple(k for k, v in ns.items() if isinstance(v, Field))
        cls._table = name.lower() + 's'
        return cls

class Model(metaclass=Meta):
    def __init__(self, **kw):
        object.__setattr__(self, '_data', {})
        for k, v in kw.items():
            setattr(self, k, v)

class User(Model):
    uid = Field(int)
    name = Field(str)

u = User(uid=1, name='ann')
print('fields', sorted(u._fields))
print('values', u._data['uid'], u._data['name'])
try:
    User(uid='x', name='ann')
except TypeError as e:
    print('rejected', str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# safe rows: 2
# unsafe SQL failed as expected

import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE logs (msg TEXT)')
def safe_insert(msg):
    conn.execute('INSERT INTO logs (msg) VALUES (?)', (msg,))
def unsafe_insert(msg):
    q = chr(39)
    conn.execute('INSERT INTO logs (msg) VALUES (' + q + msg + q + ')')
attack = 'x' + chr(39) + '); DROP TABLE logs; --'
safe_insert('plain')
safe_insert(attack)
print('safe rows:', conn.execute('SELECT COUNT(*) FROM logs').fetchone()[0])
try:
    unsafe_insert(attack)
except sqlite3.Error:
    print('unsafe SQL failed as expected')
conn.close()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# fields: ['a', 'b']
# metaclass: Meta
# descriptor names: a b
# mro: ['Form', 'object']

import inspect

class Field:
    def __set_name__(self, owner, name):
        self.name = name
class Meta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls._fields = [k for k, v in ns.items() if isinstance(v, Field)]
        return cls
class Form(metaclass=Meta):
    a = Field()
    b = Field()
print('fields:', sorted(Form._fields))
print('metaclass:', type(Form).__name__)
print('descriptor names:', Form.a.name, Form.b.name)
print('mro:', [c.__name__ for c in inspect.getmro(Form)])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sqlite3
class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError(self.name + ' expects ' + self.typ.__name__)
        obj._data[self.name] = value
class Meta(type):
    def __new__(m, name, bases, ns):
        cls = super().__new__(m, name, bases, ns)
        cls.fields = tuple(k for k, v in ns.items() if isinstance(v, Field))
        cls.table = name.lower() + 's'
        return cls
class Model(metaclass=Meta):
    def __init__(self, **kw):
        object.__setattr__(self, '_data', {})
        errors = []
        for k, v in kw.items():
            try:
                setattr(self, k, v)
            except TypeError as e:
                errors.append(str(e))
        if errors:
            raise ValueError('; '.join(errors))
    def stmt(self):
        marks = ', '.join('?' for _ in self.fields)
        return 'INSERT INTO ' + self.table + ' (' + ', '.join(self.fields) + ') VALUES (' + marks + ')'
class User(Model):
    uid = Field(int)
    name = Field(str)
conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE users (uid INTEGER, name TEXT)')
u = User(uid=1, name='ann')
conn.execute(u.stmt(), tuple(u._data[k] for k in u.fields))
print('rows', conn.execute('SELECT * FROM users').fetchall())
try:
    User(uid='x', name=1)
except ValueError as e:
    print('errors', str(e))
conn.close()
