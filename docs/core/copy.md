---
title: 第 057 讲 · 可变性、深浅拷贝与共享状态
description: 在接口边界上控制对象所有权
---

<StageHeader stage='L5 · 核心机制' level='★★★☆☆' time='30 分钟' goal='在接口边界上控制对象所有权' prereq='第 056 讲 · 属性访问链路与 __getattribute__' />

# 第 057 讲 · 可变性、深浅拷贝与共享状态

属性访问能精确定位到一份状态了，紧跟着的问题是：这份状态归谁。放多个线程进去之前，得先在单线程里把可变性、拷贝与归属三件事分开，否则「同时改它」只会把含糊放大成事故。一个平和的画面：函数把内部列表返回出去，调用方随手追加一项，你的私有数据跟着变了；一份配置字典传给几个模块，谁动过都对不上账。

由浅往深：先看赋值与浅拷贝为何仍共享内部对象，再看 deepcopy 如何维护记忆表处理循环结构，接着谈不可变的好处，最后落到接口边界上的所有权与防御性拷贝。前置是容器、函数传参与引用的概念；读完后你能在库的边界决定返回副本还是只读视图，把对象所有权讲清楚。


## 上一个用户的筛选条件串到了下一个请求

配置中心返回一个嵌套字典，业务代码把它存进实例后顺手 return 给调用方；调用方改了一个内层列表，结果另一个请求的默认值跟着变了，线上出现「上一个用户的筛选条件串到下一个用户」。第一反应是「函数返回前 copy 一下」，于是用 `copy.copy` 包了一层，问题仍在——因为内层容器是共享的。

再有人改成 deepcopy，功能对了但每次请求多花几毫秒，压测 QPS 掉了一截；还有人在有循环引用的对象图上 deepcopy，发现结果里同一个节点被复制成了两份，破坏了 aliasing。更隐蔽的是把内部 list 直接暴露给外部，或返回 MappingProxyType 后仍试图改它。

这些都不是「要不要拷贝」一句话能定的：赋值、浅拷贝、深拷贝在共享范围、循环处理、性能与所有权语义上完全不同，接口边界上必须先说清楚谁拥有这个对象。

<Callout type="warn" title='先看一个真实会出错的写法' text='[[0] * 3] * 3 改了一行，三行全变：外层乘法复制的是同一个内层列表的引用，而不是内容' />


## 赋值、浅拷贝、深拷贝各共享到哪一层

赋值 `a = b` 不复制任何东西，只让两个名字引用同一个对象，`id(a)` == `id(b)`。`copy.copy(x)` 生成一个新的最外层容器，但把内部元素的引用原样塞进去：对 list/dict/set 分别走 _copy_list / _copy_dict 等快捷路径，等价于 x[:] 或 `dict(x)`；

因此改外层互不影响，改 x[0] 指向的可变对象会双向可见。

`copy.deepcopy(x, memo=None)` 递归复制所有可变子对象，并用一个 memo 字典记录 `id(原对象)` 到 新对象 的映射：既让循环引用不会无限递归，也保证原图中被多处引用的同一个对象在结果里仍是同一个新对象（保留 aliasing）。

对 int、str、bytes、float、bool、None、函数、类型等不可变原子对象，deepcopy 走 _deepcopy_atomic 直接返回原对象，不分配内存；对只含不可变元素的 tuple，`copy.copy` 也直接返回自身。故 deepcopy 的开销集中在可变容器的数量与深度，而非对象的值大小。

**赋值 / 浅拷贝 / 深拷贝的共享范围**

| 方式 | 最外层对象 | 内层可变对象 | 循环引用 | 原子不可变对象 |
| --- | --- | --- | --- | --- |
| b = a | 同一对象，id 相同 | 完全共享 | 不涉及 | 同一对象 |
| copy.copy(a) | 新建，id 不同 | 仍共享引用 | 不递归，不处理 | 通常返回原对象 |
| copy.deepcopy(a) | 新建 | 递归新建，隔离 | 靠 memo 处理且保留 aliasing | 走 _deepcopy_atomic 直接复用 |

<ConceptDiagram type='layers3' title='第 057 讲 · 三种复制层次的共享边界' labels='三种复制层次的共享边界|copy / deepcopy 协议与不可 |接口所有权：防御性拷贝与不可变替代' caption='在接口边界上控制对象所有权' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 对照：一次 copy.copy 为什么没隔离嵌套配置

```python
import copy

inner = [1, 2]
outer = [inner, inner]
shallow = copy.copy(outer)
deep = copy.deepcopy(outer)
print('outer is shallow', outer is shallow)
print('shallow inner shared', shallow[0] is outer[0])
print('deep inner new', deep[0] is not outer[0])
print('deep keeps alias', deep[0] is deep[1])
outer[0].append(3)
print('shallow sees', shallow[0])
print('deep isolated', deep[0])
```

<OutputBox title='主示例运行结果' output='outer is shallow False\nshallow inner shared True\ndeep inner new True\ndeep keeps alias True\nshallow sees [1, 2, 3]\ndeep isolated [1, 2]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import copy\n\ninner = [1, 2]\nouter = [inner, inner]\nshallow = copy.copy(outer)\ndeep = copy.deepcopy(outer)\nprint(&#39;outer is shallow&#39;, outer is shallow)\nprint(&#39;shallow inner shared&#39;, shallow[0] is outer[0])\nprint(&#39;deep inner new&#39;, deep[0] is not outer[0])\nprint(&#39;deep keeps alias&#39;, deep[0] is deep[1])\nouter[0].append(3)\nprint(&#39;shallow sees&#39;, shallow[0])\nprint(&#39;deep isolated&#39;, deep[0])' :notes='["导入 copy 模块，标准库实现复制协议", "建一个内层可变列表", "外层列表两次引用同一个 inner，制造 aliasing", "浅拷贝：只新建最外层容器", "深拷贝：递归复制并维护 memo", "外层确实是两个不同对象", "浅拷贝的内层仍与外层共用同一个列表对象", "深拷贝为每个内层建了新对象", "原图里共享的同一对象，深拷贝后仍共享同一个新对象", "改动原图的内层列表", "浅拷贝可见这次改动，证明内层共享", "深拷贝完全隔离，仍是旧值"]' title='第 057 讲 · 可变性、深浅拷贝与共享状态' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<CodeTabs :tabs='[{"label": "主示例", "code": "import copy\n\ninner = [1, 2]\nouter = [inner, inner]\nshallow = copy.copy(outer)\ndeep = copy.deepcopy(outer)\nprint(&#39;outer is shallow&#39;, outer is shallow)\nprint(&#39;shallow inner shared&#39;, shallow[0] is outer[0])\nprint(&#39;deep inner new&#39;, deep[0] is not outer[0])\nprint(&#39;deep keeps alias&#39;, deep[0] is deep[1])\nouter[0].append(3)\nprint(&#39;shallow sees&#39;, shallow[0])\nprint(&#39;deep isolated&#39;, deep[0])", "note": "三种复制层次的共享边界"}, {"label": "对照 / 进阶", "code": "import copy\n\nnode = {&#39;name&#39;: &#39;root&#39;}\nnode[&#39;self&#39;] = node\nclone = copy.deepcopy(node)\nprint(&#39;cycle ok&#39;, clone[&#39;self&#39;] is clone, clone is not node)\ns = &#39;immutable&#39;\nn = 10 ** 40\nprint(&#39;str reused&#39;, copy.deepcopy(s) is s)\nprint(&#39;int reused&#39;, copy.deepcopy(n) is n)\nt = (1, 2, 3)\nprint(&#39;tuple copy reused&#39;, copy.copy(t) is t)", "note": "copy / deepcopy 协议与不可 pickle 的边界"}]' title='两种写法切换看' />

```python
import copy
import tracemalloc

data = [[i] for i in range(2000)]
tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
copy.copy(data)
after_shallow = tracemalloc.get_traced_memory()[0]
copy.deepcopy(data)
after_deep = tracemalloc.get_traced_memory()[0]
print('shallow delta > 0', after_shallow - base > 0)
print('deep delta > shallow', (after_deep - after_shallow) > (after_shallow - base))
print('delta ratio > 5', (after_deep - after_shallow) // max(1, after_shallow - base) > 5)
tracemalloc.stop()
```

<OutputBox title='原理验证' output='shallow delta &gt; 0 True\ndeep delta &gt; shallow True\ndelta ratio &gt; 5 True' />


## deepcopy 的 memo 与回退路径

自定义类可定义 `__copy__(self)` 与 `__deepcopy__(self, memo)` 完全接管行为；

未定义时 copy 模块回退到 `copyreg.dispatch_table` 与 `__reduce_ex__(4)`：先用 `__new__` 建空实例，再递归复制 `__dict__` 或 `__slots__`。

因此一个持有 `threading.Lock`、打开的文件句柄、数据库连接、生成器或 lambda 的对象通常无法 deepcopy，会抛 TypeError: cannot pickle '_thread.lock' object 之类错误——因为 reduce 路径要 pickle 状态。

memo 参数是关键：实现 `__deepcopy__` 时必须先建空壳、立刻 memo[`id(self)`] = 新对象、再复制字段，否则自引用字段会再次递归到同一个对象。

collections 里 tuple 的深拷贝由 _deepcopy_tuple 处理，会先复制元素再判断是否所有元素都未变，若都没变则复用原 tuple。

`types.MappingProxyType` 提供只读视图，视图本身不可赋值但底层 dict 仍可被原引用修改，做「只读返回」时要连同底层一起收好或真正复制。

**copy 模块回退路径与失败信号**

| 对象特征 | 走的路径 | 典型结果 / 报错 |
| --- | --- | --- |
| list / dict / set / tuple | _copy_list 等 C 级快捷函数 | 新建容器，元素按引用或递归复制 |
| 自定义类且有 __copy__/__deepcopy__ | 直接调用钩子 | 完全由钩子决定 |
| 自定义类无钩子 | __reduce_ex__(4) + copyreg | 复制 __dict__ / __slots__ 状态 |
| 持有 _thread.lock / 文件句柄 | reduce 需 pickle 状态 | TypeError: cannot pickle '_thread.lock' object |
| lambda / 局部函数 / 生成器 | reduce 找不到可引用名 | AttributeError 或 PicklingError |

<Callout type="tip" title='核心心智模型' text='赋值 a = b 不复制任何东西，只让两个名字引用同一个对象，id(a) == id(b)。copy.copy(x) 生成一个新的最外层容器，但把内部元素的引用原样塞进去：对 list/dict/set 分别走 _copy_list / _copy_dict 等快捷路径，等价于 x[:] 或 dic' />


### 循环图里同一节点为何仍是同一个对象

```python
import copy

node = {'name': 'root'}
node['self'] = node
clone = copy.deepcopy(node)
print('cycle ok', clone['self'] is clone, clone is not node)
s = 'immutable'
n = 10 ** 40
print('str reused', copy.deepcopy(s) is s)
print('int reused', copy.deepcopy(n) is n)
t = (1, 2, 3)
print('tuple copy reused', copy.copy(t) is t)
```

<OutputBox title='对照写法：先自己猜，再点开' output='cycle ok True True\nstr reused True\nint reused True\ntuple copy reused True' guess="true" />


## _copy_dispatch 与先登记再递归

copy 模块的核心是两张分发表 _copy_dispatch 与 _deepcopy_dispatch，键是类型对象，值是对应复制函数。deepcopy 先查 _deepcopy_dispatch，命中就直接调用；

否则按序尝试：类型在 dispatch_table 中登记、对象有 `__deepcopy__`、对象支持 `__reduce_ex__`。memo 是一个普通 dict，键为 `id(x)`，值为已生成的副本；每处理一个对象先查 memo，命中直接返回，未命中就建空壳、立刻登记、再递归字段。

这套「先登记再递归」正是循环图不死循环、且同一对象在结果中仍唯一的原因。

reduce 回退路径会调用 `cls.__new__(cls)` 建空实例，再对 `__getstate__` 返回的状态做深拷贝，最后用 `__setstate__` 或更新 `__dict__` 恢复；

这也解释了为何不可 pickle 的底层资源（锁、文件、连接）会让 deepcopy 失败。小整数 -5..256 与驻留字符串本就被解释器复用，_deepcopy_atomic 再叠一层「不可变即复用」，所以深拷贝这类值时对象身份不变。

tracemalloc 能测出浅拷贝只分配一个外层列表，深拷贝还会为每个内层容器额外分配，差额与容器数量成正比。

<Term word='赋值 / 浅拷贝 / 深拷贝' text='赋值 a = b 不复制任何东西，只让两个名字引用同一个对象，id(a) == id(b)。copy.copy(x) 生成一个新的最外层容器，但把内部元素的引用原样塞进去：对 list/dict/set 分别走 _copy_list / _copy_dict 等快捷路径，等价于 x[:] 或 dict(x)；因此改外层' />

<Term word='copy 与 deepcopy 协议' text='自定义类可定义 __copy__(self) 与 __deepcopy__(self, memo) 完全接管行为；未定义时 copy 模块回退到 copyreg.dispatch_table 与 __reduce_ex__(4)：先用 __new__ 建空实例，再递归复制 __dict__ 或 __slots__。因此' />


## 接口边界的所有权：防御性拷贝与不可变替代

值语义 vs 引用语义的 bug 大多发生在边界：构造参数直接存了外部传来的 list、getter 返回内部可变结构、缓存里放了可被调用方改动的对象。三种对策按成本递增：一是文档写明所有权（调用方不得修改），最省但最不可靠；

二是返回副本或只读视图（`list(self._items)`、`tuple(...)`、MappingProxyType），读取频繁时每次复制有开销；

三是把内部状态整体换成不可变结构（tuple、frozenset、具名元组、不可变 `dataclass(frozen=True)`），从根上消除共享写。

性能敏感路径可让 deepcopy 只作用于真正需要隔离的层级，或用「写时复制」：平时共享，修改时才复制。还要注意 list 乘法陷阱：[[0] * 3] * 3 得到三个指向同一内层 list 的引用，改一行会连改三行，正确写法是 [[0] * 3 for _ in `range(3)`]。

判断有没有共享，直接比较子对象身份比读代码更可靠。

**接口边界的所有权方案**

| 方案 | 做法 | 成本 | 适用场景 |
| --- | --- | --- | --- |
| 约定所有权 | 文档写明调用方不得修改返回值 | 零 | 内部可信代码，需配合评审 |
| 返回副本 | return list(self._items) | 每次读 O(n) 复制 | 读少写多、对象较小 |
| 只读视图 | types.MappingProxyType(d) | 零复制，但底层引用仍能改 | 配置项、元数据字典 |
| 不可变状态 | tuple / frozen dataclass | 改值要整体重建 | 高频读取、需彻底消除共享写 |
| 写时复制 | 共享直到首次修改再 deepcopy | 实现复杂 | 大对象且多数调用只读 |


## 请求配置对象：构造、读取、返回三层的所有权控制

一个 Web 服务的过滤配置从配置中心拿到嵌套 dict，构造时被存进 RequestConfig，getter 既要供内部读取又要暴露给多个中间件。若构造时直接存外部引用，配置中心后续刷新会穿透进来；若 getter 返回内部 dict，某个中间件一改就污染全链路；

若每次 getter 都 deepcopy，热点路径的分配量又扛不住。下面的实现分三层：构造时做一次深拷贝取得所有权，内部读用 MappingProxyType 只读视图，对外导出才做一次可预测的深拷贝，并提供把整份配置冻结成 tuple 的入口用于缓存键。

这样每个边界的共享范围都是显式的，排查串数据时只要看是哪一个边界返回了可变引用。

```python
import copy
from types import MappingProxyType

class RequestConfig:
    def __init__(self, raw):
        object.__setattr__(self, '_data', copy.deepcopy(raw))
    @property
    def view(self):
        return MappingProxyType(object.__getattribute__(self, '_data'))
    def export(self):
        return copy.deepcopy(object.__getattribute__(self, '_data'))
    def freeze(self):
        d = object.__getattribute__(self, '_data')
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in d.items()))
    def __setattr__(self, name, value):
        raise AttributeError('use export() to get a mutable copy')

if __name__ == '__main__':
    raw = {'tags': ['a', 'b'], 'limit': 10}
    cfg = RequestConfig(raw)
    raw['tags'].append('hack')
    print('isolated', cfg.view['tags'])
    v = cfg.export()
    v['tags'].append('local')
    print('export isolated', cfg.view['tags'])
    print('frozen', cfg.freeze())
    try:
        cfg.view['x'] = 1
    except TypeError as e:
        print('view read only', type(e).__name__)
```

<Callout type="idea" title='落地提示' text='库 API 返回副本或只读视图（MappingProxyType），在文档里写清所有权；性能敏感路径用不可变结构替代拷贝' />

<CheckList id='P057b' title='上线前自检' :items='["能复现并解释「[[0] * 3] * 3 改了一行，三行全变」", "能复现并解释「用 copy.copy 包一层就以为隔离了嵌套配置」", "能复现并解释「deepcopy 一个持有锁或数据库连接的对象报 TypeE」", "能用一条命令验证 赋值 / 浅拷贝 / 深拷贝", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "a=[1]; b=a; print(a is b, id(a)==id(b))"
```

把输入换成你自己的数据，观察结果是否仍符合 **赋值 / 浅拷贝 / 深拷贝** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| [[0] * 3] * 3 改了一行，三行全变 | 外层乘法复制的是同一个内层列表的引用，而不是内容 | 用列表推导 [[0] * 3 for _ in range(3)]，或逐行 deepcopy |
| 用 copy.copy 包一层就以为隔离了嵌套配置 | 浅拷贝只复制最外层，内层 dict/list 仍与调用方共享 | 对嵌套结构用 copy.deepcopy，或把内部状态改为 tuple / frozen dataclass 从根上不可变 |
| deepcopy 一个持有锁或数据库连接的对象报 TypeError | 无 __deepcopy__ 时回退到 __reduce_ex__，需要 pickle 状态，而锁/句柄不可 pickle | 实现 __deepcopy__ 跳过资源字段、只复制数据字段；或改成传值而非传对象 |

<Callout type="warn" title='本讲最容易踩的坑' text='[[0] * 3] * 3 改了一行，三行全变：外层乘法复制的是同一个内层列表的引用，而不是内容' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：[[0] * 3] * 3 改了一行，三行全", "body": "外层乘法复制的是同一个内层列表的引用，而不是内容", "tip": "用列表推导 [[0] * 3 for _ in range(3)]，或逐行 deepcopy"}, {"title": "第 2 步：用 copy.copy 包一层就以为隔离了嵌", "body": "浅拷贝只复制最外层，内层 dict/list 仍与调用方共享", "tip": "对嵌套结构用 copy.deepcopy，或把内部状态改为 tuple / frozen dataclass 从根上不可变"}, {"title": "第 3 步：deepcopy 一个持有锁或数据库连接的对", "body": "无 __deepcopy__ 时回退到 __reduce_ex__，需要 pickle 状态，而锁/句柄不可 pickle", "tip": "实现 __deepcopy__ 跳过资源字段、只复制数据字段；或改成传值而非传对象"}]' />


## 练习、自测与速记

<Exercise title='基础：验证浅拷贝与深拷贝的共享差异' task='构造 outer = [inner, inner]，分别做 copy.copy 与 copy.deepcopy，用 is 判断外层、内层、以及结果内部两元素之间的身份，并解释 deep keeps alias 为什么为真。' solution='import copy\ninner = [1]\nouter = [inner, inner]\na, b = copy.copy(outer), copy.deepcopy(outer)\nprint(&#39;outer&#39;, a is outer, b is outer)\nprint(&#39;inner shared&#39;, a[0] is inner, b[0] is inner)\nprint(&#39;alias kept&#39;, b[0] is b[1], a[0] is a[1])' explain='浅拷贝外层新、内层仍指向 inner；深拷贝内层也新建，但 memo 保证原图里同一个 inner 只被复制一次，所以 b[0] 与 b[1] 仍是同一个新对象。' />

<Exercise title='进阶：为含循环引用的节点实现 __deepcopy__' task='定义 Node，含 name、children 列表与 parent 回指；实现 __deepcopy__ 要求先建空壳并登记 memo，再复制字段，最后验证 clone.children[0].parent is clone。' solution='import copy\nclass Node:\n    def __init__(self, name):\n        self.name = name\n        self.children = []\n        self.parent = None\n    def __deepcopy__(self, memo):\n        new = Node(self.name)\n        memo[id(self)] = new\n        new.children = [copy.deepcopy(c, memo) for c in self.children]\n        new.parent = copy.deepcopy(self.parent, memo)\n        return new\nroot = Node(&#39;r&#39;)\nchild = Node(&#39;c&#39;)\nroot.children.append(child)\nchild.parent = root\ncl = copy.deepcopy(root)\nprint(cl is not root, cl.children[0].parent is cl, cl.children[0] is not child)' explain='必须先 memo[id(self)] = new 再递归 children，否则 child.parent 回到 root 时会重新复制 root，形成无限递归或产生两份根；登记后回指解析到同一个新根。' />

<Quiz no='057-1' q='关于 copy.deepcopy 的 memo，下列哪项准确？' :options='["它按 id 记录已复制对象，既防循环递归又保留原图里的 aliasing", "它只是缓存以加速，对结果身份没有影响", "它只对 dict 生效", "它会被每次调用自动清空，因此无法跨调用复用"]' answer="0" explain='memo 的键是 id(原对象)，值是新对象；先查表、再建空壳登记、后递归字段。因此循环不会死循环，且被多处引用的同一对象在结果中仍是同一个新对象。' />

<Quiz no='057-2' q='deepcopy 一个持有 threading.Lock 但无 __deepcopy__ 的对象，最可能怎样？' :options='["回退到 __reduce_ex__ 要 pickle 状态，抛 TypeError", "自动跳过锁字段并成功复制", "返回一个共享同一个锁的副本", "复制出第二个可用的锁"]' answer="0" explain='锁、文件句柄、连接等不可 pickle；无钩子时 reduce 路径失败并抛 TypeError: cannot pickle &#39;_thread.lock&#39; object。应实现 __deepcopy__ 只复制数据字段。' />

<Quiz no='057-3' q='关于不可变对象与 copy，正确的是？' :options='["deepcopy 大整数、字符串、只含不可变元素的 tuple 往往直接返回原对象", "deepcopy 一定为任何对象分配新内存", "copy.copy(tuple) 总是新建 tuple", "MappingProxyType 会连同底层 dict 一起复制"]' answer="0" explain='_deepcopy_atomic 把不可变原子类型映射为恒等；copy.copy 对 tuple 也走 _copy_immutable 返回自身。MappingProxyType 只是视图，底层 dict 仍在原引用手里。' />

<Predict no='057-P' q='t = (1, 2, 3); copy.copy(t) is t 与 copy.deepcopy(10 ** 40) is 原整数，结果分别是？' :options='["True 与 True，两者都复用原对象", "False 与 False，都新建", "True 与 False", "False 与 True"]' answer='0' output='True True' explain='tuple 不可变，_copy_immutable 让 copy.copy 直接返回自身；大整数是原子不可变类型，_deepcopy_atomic 同理。是否「复用」取决于类型是否可变，而非对象大小。' />

<FillBlank no='057-F' tpl='___ copy' :answers='["import"]' hint='回想本讲关于 赋值 / 浅拷贝 / 深拷贝 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 三种复制层次的共享边界 的落点。' />

<KnowledgeCard :points='["赋值只加引用；copy.copy 新建最外层、内层仍共享；copy.deepcopy 递归复制并靠 memo 保留 aliasing", "memo 按 id 映射，实现 __deepcopy__ 必须「建空壳 → 登记 memo → 再递归字段」，否则循环引用会炸", "deepcopy 回退路径是 __reduce_ex__(4) + copyreg，遇到锁/文件/连接会抛 cannot pickle 的 TypeError", "不可变原子对象（int/str/bytes/None/函数）与只含不可变元素的 tuple 通常被直接复用，不分配内存", "接口边界要明确所有权：返回副本、MappingProxyType 只读视图、或整体换成 tuple / frozen dataclass", "[[0]*3]*3 共享同一个内层列表；用列表推导生成独立行；tracemalloc 可量化浅/深拷贝的分配差额"]' :pitfalls='["[[0] * 3] * 3 改了一行，三行全变", "用 copy.copy 包一层就以为隔离了嵌套配置", "deepcopy 一个持有锁或数据库连接的对象报 TypeError", "把内部可变结构直接返回给调用方，对方一改就等于改了你的私有状态"]' summary='浅拷贝只复制最外层容器，内部对象仍共享；深拷贝递归复制并维护记忆表以处理循环引用' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 赋值只加引用；copy.copy 新建最外层、内层仍共享；copy.deepcopy 递归复制并靠 memo 保留 aliasing | 建立直觉 |
| memo 按 id 映射，实现 __deepcopy__ 必须「建空壳 → 登记 memo → 再递归字段」，否则循环引用会炸 | 跑通示例 |
| deepcopy 回退路径是 __reduce_ex__(4) + copyreg，遇到锁/文件/连接会抛 cannot pickle 的 TypeError | 深入边界 |
| 不可变原子对象（int/str/bytes/None/函数）与只含不可变元素的 tuple 通常被直接复用，不分配内存 | 工程落地 |
| 接口边界要明确所有权：返回副本、MappingProxyType 只读视图、或整体换成 tuple / frozen dataclass | 随堂检测 |
| [[0]*3]*3 共享同一个内层列表；用列表推导生成独立行；tracemalloc 可量化浅/深拷贝的分配差额 | 复盘 |

1. 赋值只加引用；copy.copy 新建最外层、内层仍共享；copy.deepcopy 递归复制并靠 memo 保留 aliasing

2. memo 按 id 映射，实现 __deepcopy__ 必须「建空壳 → 登记 memo → 再递归字段」，否则循环引用会炸

3. deepcopy 回退路径是 __reduce_ex__(4) + copyreg，遇到锁/文件/连接会抛 cannot pickle 的 TypeError

[下一讲：性能剖析：timeit、cProfile 与 tracemalloc](/core/profiling)
