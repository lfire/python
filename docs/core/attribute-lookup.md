---
title: 第 056 讲 · 属性访问链路与 __getattribute__
description: 解释所有属性相关现象的统一模型
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='35 分钟' goal='解释所有属性相关现象的统一模型' prereq='第 055 讲 · 导入系统源码级：finder、loader 与缓存' />

# 第 056 讲 · 属性访问链路与 __getattribute__

把导入这条查找链走通之后，代码里最常做的其实是 `obj.x`：从对象身上取一份状态。此刻仍只有一条执行流，正好把「取值」也拆成固定次序，免得日后多线程一起来连谁改了什么都分不清。你大概遇到过：给对象挂了缓存或懒加载，有时取到实例字典里的旧值，有时却落到类上的方法，几次结果对不上。

先从 `__getattribute__` 这个总入口说起，顺着数据描述符、实例字典、非数据描述符走到 `__getattr__` 兜底，最后看递归陷阱和它处在热路径上的开销。需要你理解类、实例字典与 MRO 上的描述符；学完能用这条链统一解释属性相关的怪现象，也能稳妥写出懒加载代理。


## 一个懒加载字段引发的 RecursionError

给 ORM 模型加一个「懒加载」字段：第一次读 `obj.profile` 时去查库，之后复用缓存。

有人把这段逻辑直接写进 `__getattribute__`，写成下面这段代码，一跑就抛 RecursionError。

```python
def __getattribute__(self, name):
    if name == 'profile':
        return load(self)
```

原因不复杂：`load(self)` 内部要读 `self.id`，而任何 `self.xxx` 都会重新进入同一个 `__getattribute__`，递归没有出口。

退一步改用 `__getattr__` 兜底，表面能跑，可一旦给实例赋值 `obj.profile = x`，缓存值就落在实例的 `__dict__` 里，把 property 的校验绕了过去。

还有人把 `@property` 与同名实例属性一起用，以为实例值会优先，结果永远读到描述符。

这几件事不是各自独立的坑，而是同一条查找链在不同位置的结果：数据描述符、实例字典、非数据描述符、`__getattr__` 各有固定优先级，中间还夹着 `__getattribute__` 这个总入口。

不把链拆开，就只能靠试错改代码。

<Callout type="warn" title='先看一个真实会出错的写法' text='在 __getattribute__ 里用 self.xxx 取别的属性：任何 self.xxx 都会再次进入 __getattribute__，形成无限递归并抛 RecursionError' />


## obj.x 的六步查找链

任何 `obj.x` 都先调用 `type(obj).__getattribute__(obj, 'x')`，object 的默认实现按固定次序解析。

第一步在 `type(obj)` 的 MRO 上查找名字，得到类属性 `cls_attr`，找不到记为 `None`；第二步若 `cls_attr` 是数据描述符，也就是类型定义了 `__set__` 或 `__delete__`，就无条件调用它的 `__get__(obj, type(obj))` 并返回，实例 `__dict__` 里的同名键完全不参与；第三步查 `obj.__dict__`，命中即返回；第四步若 `cls_attr` 是非数据描述符（只定义 `__get__`），调用它的 `__get__`；第五步 `cls_attr` 非 `None` 就直接返回类属性；第六步以上都没结果才抛 `AttributeError`，此时若类定义了 `__getattr__(self, name)`，解释器通过 `slot_tp_getattr_hook` 再调用它兜底。

由此能解释几种常见现象：`property` 是数据描述符（property 类型带一个会抛 `AttributeError` 的 `__set__`），实例字典盖不住它；函数对象是非数据描述符（只有 `__get__`），因此实例属性可以遮蔽同名方法；`staticmethod` 与 `classmethod` 同样是非数据描述符。

`__slots__` 声明的属性是类上的 `member_descriptor`，也属于数据描述符，且实例通常不再有 `__dict__`。

**obj.x 六步查找链的命中条件**

| 次序 | 检查对象 | 命中条件 | 结果 |
| --- | --- | --- | --- |
| 1 | type(obj) 的 MRO | 找到类属性 cls_attr | 暂存，不立即返回 |
| 2 | cls_attr 是数据描述符 | 类型含 __set__ 或 __delete__ | 调用 __get__(obj, type)，实例字典被跳过 |
| 3 | obj.__dict__ | 存在同名键 | 返回实例值，可遮蔽非数据描述符 |
| 4 | cls_attr 是非数据描述符 | 只有 __get__ | 调用 __get__(obj, type) |
| 5 | cls_attr 非 None | 普通类属性 | 直接返回类属性对象 |
| 6 | 以上皆空 | 触发 AttributeError | 若定义 __getattr__ 则调用它兜底 |

<ConceptDiagram type='flow4' title='第 056 讲 · obj.x 的完整优先级链' labels='obj.x 的完整优先级链|__getattribute__ 的递归与…|描述符协议、cached_property…|性能与递归风险' caption='解释所有属性相关现象的统一模型' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='任何 `obj.x` 都先调用 `type(obj).__getattribute__(obj, &#39;x&#39;)`，object 的默认实现按固定次序解析。第一步在 `type(obj)` 的 MRO 上查找名字，得到类属性 `cls_attr`，找不到记为 `None`；第二步若 `cls_attr`…' />


## __getattribute__ 的递归与 __setattr__ 对称性

覆盖 `__getattribute__` 时，方法体内任何 `self.xxx`、`getattr(self, ...)`、甚至访问 `self.__dict__`，都会再次触发 `__getattribute__`，形成无限递归，最终抛 `RecursionError`（报错文字是 maximum recursion depth exceeded）。

唯一安全的底座是 `object.__getattribute__`，它执行上一段那六步而不回调你的覆盖；需要拦截的分支单独判断，其余一律委托给它。

因为它在每次属性访问的热路径上，拦截逻辑应尽量薄：只判断少量名字，重计算放到函数或缓存里。

赋值侧对称地有 `__setattr__`，所有 `self.x = v` 都经过它，内部必须用 `object.__setattr__` 委托，否则同样递归；数据描述符的 `__set__` 也由 `object.__setattr__` 负责分派，所以给 property 赋值会走 setter 而不是写实例字典。

`del obj.x` 对应 `__delattr__` 与描述符的 `__delete__`。

`inspect.getattr_static`（3.2+）能绕过整条动态链拿到类上的原始对象，是调试「值到底从哪来」的关键工具，它不会触发 `__get__`。

```python
class DataDesc:
    def __get__(self, obj, owner):
        return 'data-desc'
    def __set__(self, obj, value):
        pass

class NonDataDesc:
    def __get__(self, obj, owner):
        return 'non-data-desc'

class Demo:
    a = DataDesc()
    b = NonDataDesc()

d = Demo()
d.__dict__['a'] = 'instance-a'
d.__dict__['b'] = 'instance-b'
print(d.a)
print(d.b)
d.b = 'assigned'
print(d.b)
print(type(Demo.__dict__['a']).__name__, hasattr(DataDesc, '__set__'))
```

<OutputBox title='主示例运行结果' output='data-desc\ninstance-b\nassigned\nDataDesc True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class DataDesc:\n    def __get__(self, obj, owner):\n        return &#39;data-desc&#39;\n    def __set__(self, obj, value):\n        pass\n\nclass NonDataDesc:\n    def __get__(self, obj, owner):\n        return &#39;non-data-desc&#39;\n\nclass Demo:\n    a = DataDesc()\n    b = NonDataDesc()\n\nd = Demo()\nd.__dict__[&#39;a&#39;] = &#39;instance-a&#39;\nd.__dict__[&#39;b&#39;] = &#39;instance-b&#39;\nprint(d.a)\nprint(d.b)\nd.b = &#39;assigned&#39;\nprint(d.b)\nprint(type(Demo.__dict__[&#39;a&#39;]).__name__, hasattr(DataDesc, &#39;__set__&#39;))' :notes='["定义数据描述符类型，带 __set__", "数据描述符的 __get__", "返回固定串，供对比谁被命中", "有 __set__ 即成为数据描述符", "方法体留空，赋值会被分派到这里", "空行，只用于分隔逻辑块，不影响执行结果。", "定义非数据描述符类型，只有 __get__", "非数据描述符的 __get__", "仅在实例字典未命中时被调用", "空行，只用于分隔逻辑块，不影响执行结果。", "把两个描述符挂到类上作类属性", "a 是数据描述符实例", "b 是非数据描述符实例", "空行，只用于分隔逻辑块，不影响执行结果。", "创建实例，此时 __dict__ 为空", "绕过动态链，直接塞同名键 a", "同样塞同名键 b，检验谁优先", "a 仍读到数据描述符，实例字典被跳过", "b 命中实例字典，非数据描述符被遮蔽", "给 b 赋值：非数据描述符没有 __set__", "赋值写入实例字典，读到刚写的值", "用 __dict__ 取原始类属性，确认类型与 __set__"]' title='第 056 讲 · 属性访问链路与 __getattribute__' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Term word='__getattribute__ 总入口' text='任何 `obj.x` 都先调用 `type(obj).__getattribute__(obj, &#39;x&#39;)`，object 的默认实现按固定次序解析。第一步在 `type(obj)` 的 MRO 上查找名字，得到类属性 `cls_attr`，找不到记为 `None`；第二步若 `cls_attr` 是数据描述符，也就是…' />

<Term word='数据描述符优先' text='覆盖 `__getattribute__` 时，方法体内任何 `self.xxx`、`getattr(self, ...)`、甚至访问 `self.__dict__`，都会再次触发 `__getattribute__`，形成无限递归，最终抛 `RecursionError`（报错文字是 maximum recursio…' />


## 对照：__getattr__ 兜底为何绕过校验

```python
class Lazy:
    def __init__(self):
        object.__setattr__(self, 'cache', {})
    def __getattribute__(self, name):
        if name.startswith('computed_'):
            return 'lazy:' + name
        return object.__getattribute__(self, name)
    def __getattr__(self, name):
        return 'fallback:' + name

x = Lazy()
print(x.computed_total)
print(x.cache)
print(x.missing)
print(x.__dict__['cache'] == {})
```

<OutputBox title='对照写法：先自己猜，再点开' output='lazy:computed_total\n{}\nfallback:missing\nTrue' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "class DataDesc:\n    def __get__(self, obj, owner):\n        return &#39;data-desc&#39;\n    def __set__(self, obj, value):\n        pass\n\nclass NonDataDesc:\n    def __get__(self, obj, owner):\n        return &#39;non-data-desc&#39;\n\nclass Demo:\n    a = DataDesc()\n    b = NonDataDesc()\n\nd = Demo()\nd.__dict__[&#39;a&#39;] = &#39;instance-a&#39;\nd.__dict__[&#39;b&#39;] = &#39;instance-b&#39;\nprint(d.a)\nprint(d.b)\nd.b = &#39;assigned&#39;\nprint(d.b)\nprint(type(Demo.__dict__[&#39;a&#39;]).__name__, hasattr(DataDesc, &#39;__set__&#39;))", "note": "obj.x 的完整优先级链"}, {"label": "对照 / 进阶", "code": "class Lazy:\n    def __init__(self):\n        object.__setattr__(self, &#39;cache&#39;, {})\n    def __getattribute__(self, name):\n        if name.startswith(&#39;computed_&#39;):\n            return &#39;lazy:&#39; + name\n        return object.__getattribute__(self, name)\n    def __getattr__(self, name):\n        return &#39;fallback:&#39; + name\n\nx = Lazy()\nprint(x.computed_total)\nprint(x.cache)\nprint(x.missing)\nprint(x.__dict__[&#39;cache&#39;] == {})", "note": "__getattribute__ 的递归与 __setattr__ 的对称性"}]' title='两种写法对照' note='差异集中在 __getattribute__ 总入口；先看输出，再找背后的规则。' />

```python
import dis
import inspect

class D:
    def __get__(self, o, t):
        return 100

class C:
    x = D()

def read(o):
    return o.x

c = C()
print('static', inspect.getattr_static(c, 'x') is C.__dict__['x'])
print('dynamic', c.x)
print('opnames', [i.opname for i in dis.get_instructions(read)])
```

<OutputBox title='原理验证' output='static True\ndynamic 100\nopnames [&#39;RESUME&#39;, &#39;LOAD_FAST&#39;, &#39;LOAD_ATTR&#39;, &#39;RETURN_VALUE&#39;]' />


## 描述符协议与数据描述符的优先级

描述符是类属性里实现了 `__get__`、`__set__` 或 `__delete__` 任一方法的对象；`__set_name__`（3.6+）在类创建时由 `type.__new__` 自动调用，可省去手写字段名。区分数据与非数据只看有没有 `__set__` 或 `__delete__`，与 `__get__` 无关。

`functools.cached_property`（3.8+）刻意做成非数据描述符：首次访问计算后把结果写进实例的 `__dict__`，此后实例字典优先命中，描述符不再执行，等价于「一次性懒加载且可被覆盖」；代价是实例必须有 `__dict__`（与 `__slots__` 冲突），而且它不是线程安全的。

远程属性、ORM 懒加载、代理对象应优先用 `__getattr__` 实现：只在正常查找彻底失败时被调用，不拖慢已有属性的访问。

若确实要拦截所有访问（审计、透明代理），用 `__getattribute__` 并全程委托 `object.__getattribute__`，同时用 `inspect.getattr_static` 和 `dis` 验证分派路径。

**常见描述符类型与优先级归类**

| 描述符 | 是否有 __set__/__delete__ | 归类 | 实例字典能否遮蔽 |
| --- | --- | --- | --- |
| property | 有（setter 缺失时 __set__ 抛 AttributeError） | 数据描述符 | 不能 |
| __slots__ 的 member_descriptor | 有 | 数据描述符 | 不能，且实例无 __dict__ |
| 普通函数 / method | 无 | 非数据描述符 | 能，实例属性可遮蔽同名方法 |
| staticmethod / classmethod | 无 | 非数据描述符 | 能 |
| functools.cached_property (3.8+) | 无 | 非数据描述符 | 能，首次计算后写 __dict__ 自遮蔽 |

**属性协议方法与递归安全写法**

| 方法 | 触发时机 | 内部安全底座 | 误用后果 |
| --- | --- | --- | --- |
| __getattribute__(self, name) | 每一次 obj.x / getattr | object.__getattribute__(self, name) | 体内用 self.x 即无限递归 RecursionError |
| __getattr__(self, name) | 仅正常查找抛 AttributeError 后 | 直接返回或 raise AttributeError | 拦截已有属性会失效，且掩盖拼写错误 |
| __setattr__(self, name, value) | 每一次 obj.x = v | object.__setattr__(self, name, value) | 体内赋值自身即递归 |
| inspect.getattr_static (3.2+) | 显式调用 | 不触发 __get__ | 拿不到动态计算值，但能定位原始类属性 |


## _PyObject_GenericGetAttrWithDict 的执行路径

在 CPython 里，实例属性解析由 `Objects/object.c` 的 `_PyObject_GenericGetAttrWithDict` 完成：它先在类型的 MRO 上做 `_PyType_Lookup` 得到 descr，再用 `PyDescr_IsData` 判断 descr 类型是否带 `tp_descr_set`，成立就调 `descr.__get__`；否则查实例字典，再处理非数据 descr 的 `__get__`，最后返回 descr 或抛 `AttributeError`。

类型对象创建时 `type.__new__` 会扫描命名空间里带 `__set_name__` 的描述符并回调，让描述符知道自己的属性名。

`__getattribute__` 的插槽是 `tp_getattro`：用户类覆盖它后，`slot_tp_getattr_hook` 还会在 `AttributeError` 时转去 `tp_getattr`（也就是 `__getattr__`），这一层包装正是「`__getattr__` 只作兜底」的实现来源。

`LOAD_ATTR` 字节码在 3.11+ 有自适应特化缓存，命中稳定类型时会内联查字典，但语义仍等价于上述六步。property 用 C 实现且带会报错的 `__set__`，因此恒为数据描述符；函数对象的 `__get__` 负责把函数绑定成 bound method，它没有 `__set__`，所以是典型的非数据描述符。


## ORM 懒加载字段与属性错因速查

一个模型对象有 id、name 等普通列，profile 字段来自另一张表，希望第一次读才查库、之后读缓存；同时 profile 的赋值必须走校验。

若把逻辑写进 `__getattribute__`，读取 `self.id` 也会递归；若用普通实例属性缓存，又会被后续赋值绕过校验。

正确的分工是：校验交给 `property`（数据描述符，保证 setter 生效），懒加载与未知字段交给 `__getattr__`（只在正常链失败时触发），缓存写进实例的 `__dict__`，由 property 的读路径读取。

下面的片段把这三种机制组合成一个可运行的最小模型，并用 `__getattribute__` 只做一层薄薄的访问计数，所有真实取属性都委托给 `object.__getattribute__`，避免递归。

```python
class Model:
    def __init__(self, rowid):
        object.__setattr__(self, 'rowid', rowid)
        object.__setattr__(self, '_hits', 0)
    def __getattribute__(self, name):
        if not name.startswith('_'):
            object.__setattr__(self, '_hits', object.__getattribute__(self, '_hits') + 1)
        return object.__getattribute__(self, name)
    @property
    def profile(self):
        d = object.__getattribute__(self, '__dict__')
        if '_profile' not in d:
            d['_profile'] = 'profile-of-' + str(d['rowid'])
        return d['_profile']
    @profile.setter
    def profile(self, value):
        if not isinstance(value, str):
            raise TypeError('profile must be str')
        self.__dict__['_profile'] = value
    def __getattr__(self, name):
        if name.startswith('col_'):
            return 'from-db:' + name
        raise AttributeError(name)

if __name__ == '__main__':
    m = Model(7)
    print(m.profile)
    m.profile = 'edited'
    print(m.profile, m.col_extra)
    try:
        m.missing
    except AttributeError as e:
        print('missing', type(e).__name__)
```

<Callout type="idea" title='落地提示' text='代理对象、懒加载、远程属性用 __getattr__ 实现；不要滥改 __getattribute__，它位于每次属性访问的热路径上' />

<CheckList id='P056a' title='上线前自检' :items='["能复现并解释「在 __getattribute__ 里用 self.xxx…」", "能复现并解释「给实例塞同名属性想覆盖 property 的校验」", "能复现并解释「用 hasattr / getattr 判断属性是否存在就万…」", "能用一条命令验证 __getattribute__ 总入口", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在 __getattribute__ 里用 self.xxx 取别的属性 | 任何 self.xxx 都会再次进入 __getattribute__，形成无限递归并抛 RecursionError | 只在少量名字上拦截，其余一律 return object.__getattribute__(self, name) |
| 给实例塞同名属性想覆盖 property 的校验 | property 是数据描述符，优先级高于实例 __dict__，实例值永远读不到且赋值会走 setter | 把可变状态存进 property 的 setter 管理的私有字段，或改用非数据描述符 / cached_property |
| 用 hasattr / getattr 判断属性是否存在就万事大吉 | hasattr 只吞 AttributeError，property 的 __get__ 里抛 ValueError 会照常冒泡；__getattr__ 还会让拼错的名字返回假值 | 用 inspect.getattr_static 定位真实类属性，让 __getattr__ 对未知名字 raise AttributeError 而非静默返回 |

<Callout type="warn" title='本讲最容易踩的坑' text='在 __getattribute__ 里用 self.xxx 取别的属性：任何 self.xxx 都会再次进入 __getattribute__，形成无限递归并抛 RecursionError' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在 __getattribute__ 里用…", "body": "任何 self.xxx 都会再次进入 __getattribute__，形成无限递归并抛 RecursionError", "tip": "只在少量名字上拦截，其余一律 return object.__getattribute__(self, name)"}, {"title": "第 2 步：给实例塞同名属性想覆盖 property 的…", "body": "property 是数据描述符，优先级高于实例 __dict__，实例值永远读不到且赋值会走 setter", "tip": "把可变状态存进 property 的 setter 管理的私有字段，或改用非数据描述符 / cached_property"}, {"title": "第 3 步：用 hasattr / getattr 判断…", "body": "hasattr 只吞 AttributeError，property 的 __get__ 里抛 ValueError 会照常冒泡；__getattr__ 还会让拼错的名字返回假值", "tip": "用 inspect.getattr_static 定位真实类属性，让 __getattr__ 对未知名字 raise AttributeError 而非静默返回"}]' />


## 练习、自测与速记

<Exercise title='基础：证明数据描述符盖住实例字典' task='定义带 __set__ 的描述符与只有 __get__ 的描述符各一个，挂到同一类上，再往实例 __dict__ 写同名键，分别读取并解释差异。' solution='class DD:\n    def __get__(self, o, t): return &#39;dd&#39;\n    def __set__(self, o, v): pass\nclass ND:\n    def __get__(self, o, t): return &#39;nd&#39;\nclass C:\n    a = DD()\n    b = ND()\nc = C()\nc.__dict__[&#39;a&#39;] = &#39;inst&#39;\nc.__dict__[&#39;b&#39;] = &#39;inst&#39;\nprint(c.a, c.b)' explain='输出 dd inst。数据描述符有 __set__，优先级高于实例字典；非数据描述符被实例字典里的同名键遮蔽，所以读到 inst。' />

<Exercise title='进阶：写一个不递归的只读代理' task='实现 ReadOnlyProxy，包装任意对象，所有读转发给被包装对象，所有写抛 AttributeError；要求用 object.__getattribute__ 取得内部字段，并用 dis 确认读路径只有一条 LOAD_ATTR。' solution='import dis\nclass ReadOnlyProxy:\n    def __init__(self, target):\n        object.__setattr__(self, &#39;_target&#39;, target)\n    def __getattribute__(self, name):\n        if name == &#39;_target&#39;:\n            return object.__getattribute__(self, name)\n        return getattr(object.__getattribute__(self, &#39;_target&#39;), name)\n    def __setattr__(self, name, value):\n        raise AttributeError(&#39;read only&#39;)\np = ReadOnlyProxy(&#39;abc&#39;)\nprint(p.upper())\nprint([i.opname for i in dis.get_instructions(ReadOnlyProxy.__getattribute__)][:4])' explain='内部字段一律经 object.__getattribute__ 获取，避免二次进入覆盖方法；写操作在 __setattr__ 直接拒绝。dis 里连续 LOAD_GLOBAL / LOAD_METHOD 说明没有隐藏的递归属性访问。' />

<Quiz no='056-1' q='实例 __dict__ 里有同名键时，下面哪个描述符仍一定被优先调用？' :options='["定义了 __set__ 的 property", "只有 __get__ 的函数对象", "functools.cached_property", "普通类属性 int"]' answer="0" explain='数据描述符（含 __set__ 或 __delete__）排在实例字典之前；property 带 __set__，函数、cached_property 与普通类属性都会被实例字典遮蔽。' />

<Quiz no='056-2' q='覆盖 __getattribute__ 后，方法体内读取 self.other 会发生什么？' :options='["再次进入 __getattribute__，无限递归直到 RecursionError", "自动走 object 默认实现，正常返回", "抛 AttributeError", "返回 None"]' answer="0" explain='所有 self.xxx 都经过 tp_getattro 即被覆盖的方法。必须显式 return object.__getattribute__(self, name) 作为底座，拦截逻辑只处理少量名字。' />

<Quiz no='056-3' q='关于 __getattr__ 与 inspect.getattr_static，正确的是？' :options='["__getattr__ 仅在正常查找抛 AttributeError 后被调；getattr_static 不触发描述符 __get__", "__getattr__ 比实例字典优先", "getattr_static 会执行 property 的 fget", "定义 __getattr__ 后 hasattr 恒为 True 且无法改"]' answer="0" explain='slot_tp_getattr_hook 只在 AttributeError 时转 __getattr__；getattr_static 直接读 MRO 与 __dict__，绕过 __get__，适合定位「值到底从哪来」。' />

<Predict no='056-4' q='类上有 @property def x(self): return 1，实例执行 obj.__dict__[&#39;x&#39;] = 9 后读 obj.x，结果是？' :options='["1，property 是数据描述符，实例字典被跳过", "9，实例字典优先", "抛 AttributeError", "取决于 Python 版本"]' answer='0' output='1' explain='property 类型定义了 __set__，属于数据_descriptor，查找链第 2 步就调用它的 __get__，第 3 步的实例字典根本不会被执行；赋值也会走 setter 而非写字典。' />

<FillBlank no='056-5' tpl='___ __get__(self, obj, owner):' :answers='["def"]' hint='回想本讲关于 __getattribute__ 总入口 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 obj.x 的完整优先级链 的落点。' />

<KnowledgeCard :points='["obj.x 的统一入口是 type(obj).__getattribute__；六步顺序为数据描述符 → 实例 __dict__ → 非数据描述符 → 类属性 → __getattr__", "数据描述符指类型带 __set__ 或 __delete__；property 与 __slots__ 成员是数据描述符，函数、staticmethod、cached_property 不是", "__getattribute__ 内任何 self.xxx 都会递归，唯一底座是 object.__getattribute__；__setattr__ 对称地委托 object.__setattr__", "__getattr__ 只在 AttributeError 后兜底，适合懒加载与代理；inspect.getattr_static 绕过 __get__ 可定位原始属性", "cached_property (3.8+) 是非数据描述符，首次算完写实例 __dict__ 自我遮蔽，与 __slots__ 冲突且非线程安全", "LOAD_ATTR 在 3.11+ 有自适应特化缓存，语义仍等价于 _PyObject_GenericGetAttrWithDict 的六步"]' :pitfalls='["在 __getattribute__ 里用 self.xxx 取别的属性", "给实例塞同名属性想覆盖 property 的校验", "用 hasattr / getattr 判断属性是否存在就万事大吉", "在 __getattribute__ 里用 self.x 取属性会无限递归，必须用 object.__getattribute__"]' summary='一次 obj.x 要依次问：类及其 MRO 上的数据描述符、实例 __dict__、非数据描述符、最后才是 __getattr__，所有属性现象都由这条链解释' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| obj.x 的统一入口是 type(obj).__getattribute__；六步顺序为数据描述符 → 实例 __dict__ → 非数据描述符 → 类属性 → __getattr__ | 建立直觉 |
| 数据描述符指类型带 __set__ 或 __delete__；property 与 __slots__ 成员是数据描述符，函数、staticmethod、cached_property 不是 | 跑通示例 |
| __getattribute__ 内任何 self.xxx 都会递归，唯一底座是 object.__getattribute__；__setattr__ 对称地委托 object.__setattr__ | 深入边界 |
| __getattr__ 只在 AttributeError 后兜底，适合懒加载与代理；inspect.getattr_static 绕过 __get__ 可定位原始属性 | 工程落地 |
| cached_property (3.8+) 是非数据描述符，首次算完写实例 __dict__ 自我遮蔽，与 __slots__ 冲突且非线程安全 | 随堂检测 |
| LOAD_ATTR 在 3.11+ 有自适应特化缓存，语义仍等价于 _PyObject_GenericGetAttrWithDict 的六步 | 复盘 |

1. obj.x 的统一入口是 type(obj).__getattribute__；六步顺序为数据描述符 → 实例 __dict__ → 非数据描述符 → 类属性 → __getattr__

2. 数据描述符指类型带 __set__ 或 __delete__；property 与 __slots__ 成员是数据描述符，函数、staticmethod、cached_property 不是

3. __getattribute__ 内任何 self.xxx 都会递归，唯一底座是 object.__getattribute__；__setattr__ 对称地委托 object.__setattr__

[下一讲：可变性、深浅拷贝与共享状态](/core/copy)

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `__getattribute__` 总入口 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/056-attribute-lookup.py`

```bash
python3 examples/lessons/056-attribute-lookup.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/056-attribute-lookup.py) · [全部示例代码索引](/examples/)
