"""
第 045 讲 · 元类：__new__、type 与类创建过程
与教程正文一一对应的示例代码

课程页面：/oop/metaclass
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/045-metaclass.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/045-metaclass.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# metaclass Registry
# registered model
# dynamic Dynamic 42
# bases ['object']

class Registry(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls.registered = name.lower()
        return cls
class Model(metaclass=Registry):
    pass

print('metaclass', type(Model).__name__)
print('registered', Model.registered)
Dynamic = type('Dynamic', (object,), {'value': 42})
print('dynamic', Dynamic.__name__, Dynamic.value)
print('bases', [b.__name__ for b in Model.__bases__])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# set_name uid
# init_subclass User
# registry ['User']
# field name uid

class Field:
    def __set_name__(self, owner, name):
        self.name = name
        print('set_name', name)
class Base:
    subclasses = []
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        Base.subclasses.append(cls.__name__)
        print('init_subclass', cls.__name__)
class User(Base):
    uid = Field()
print('registry', Base.subclasses)
print('field name', User.uid.name)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# prepare C
# type of class: False M
# is type instance: True
# MRO: ['C', 'object']

import inspect

class M(type):
    @classmethod
    def __prepare__(mcls, name, bases):
        print('prepare', name)
        return {}
class C(metaclass=M):
    pass
print('type of class:', type(C) is type, type(C).__name__)
print('is type instance:', isinstance(C, type))
print('MRO:', [c.__name__ for c in inspect.getmro(C)])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
class ModelMeta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        if name != 'Model':
            cls._columns = {}
            for k, v in ns.items():
                if isinstance(v, Field):
                    cls._columns[v.name] = v.typ.__name__
            cls._table = name.lower() + 's'
        return cls
class Model(metaclass=ModelMeta):
    pass
class User(Model):
    uid = Field(int)
    name = Field(str)
print('table', User._table)
print('columns', User._columns)
def create_sql(model):
    cols = ', '.join(k + ' ' + v.upper() for k, v in model._columns.items())
    return 'CREATE TABLE ' + model._table + ' (' + cols + ')'
print(create_sql(User))
