---
title: 第 006 讲 · 一切皆对象：id、type、value 与可变性
description: 建立 Python 对象模型的第一张心智图
---

<StageHeader stage='L1 · 编程地基' level='★☆☆☆☆' time='25 分钟' goal='建立 Python 对象模型的第一张心智图' prereq='第 005 讲 · 学习路线：十三个阶段如何递进' />

# 第 006 讲 · 一切皆对象：id、type、value 与可变性

从这里起暂别工具与环境，问个更根本的问题：都说一切皆对象，随手写的那个值究竟是什么。从这一讲起迈进编程地基；想清值的本来面目，后面一大半『怎么又串了』的疑惑会自己消解。你或许碰过：两个看着一样的列表，改一个另一个也跟着变；把名字赋给名字，本以为复制了，动一处两边都动。我们先把对象的三要素 id、type、value 立起来，接着分清 is 比身份、== 比值，再顺着可变与不可变看同一句赋值为何两种结局，最后借小整数缓存坐实直觉。能跑脚本、见过变量赋值就够；学完你能自己推明白别名、拷贝与传参，而不必死记『列表会共享』。


## 同一个值，is 有时真有时假

一段接口代码把用户等级写成 `level = 1000`，测试时 `if level is 1000:` 偶尔成立、偶尔不成立，改来改去像撞运气；

另一个函数收到一个 list 参数，往里 append 了一条日志，调用方持有的同一个列表竟然也多了一条，排查半天发现是别名穿透。还有人拿 == 去判断两个大整数是不是同一个对象，或用 is 比较从 `JSON` 里读出的字符串，结果随值的大小与来源变化。

朴素解法是「记住 is 比 == 严格」这类口诀，可一到具体值就失灵：`100 is 100` 成立，`1000 is 1000` 在同一编译单元里也可能成立，`int('1000')` 两次却一定不成立。这些现象背后只有一套模型：Python 里每个值都是堆上的对象，有身份、类型、值三要素；

名字只是贴在对象上的标签，is 比较身份、== 比较值，而 -5 到 256 的小整数与部分短字符串会被缓存复用。

本讲用 `id`、`type`、`isinstance`、`sys.getrefcount` 把这套模型变成能亲手验证的事实，并说清可变与不可变如何决定别名的后果。


## 对象三要素与 is / == 的分工

每个对象都有三个互相独立的属性：身份由 `id(obj)` 返回，CPython 里就是对象地址，进程内唯一且生命周期内不变；类型由 `type(obj)` 给出，决定对象支持哪些操作，一经创建不变；值是对象承载的数据，可变对象的值能原地改变。

is 比较的是身份，等价于 `id(a) == id(b)`，中间不做任何类型转换或值比较；== 比较的是值，实际调用左操作数的 `__eq__`（可被重载），所以自定义类能定义自己的相等语义，NumPy 数组之间 == 甚至返回数组而非布尔。

由此得到一条硬规则：is 只用于判断单例对象——None、True、False、Ellipsis 与 NotImplemented，这些在解释器里全局只有一个实例；任何「值是否相等」的判断都必须用 ==。

用 is 比值会踩到对象池：CPython 预创建 -5 到 256 的整数，赋值命中范围就直接复用池里的实例，短字符串与标识符会驻留，于是 `a = 100` 后 `b = 100` 常 is 成立，而两次 `int('1000')` 各新建对象则 is 不成立。

更隐蔽的是同一编译单元里相同字面量会被编译器合并进 co_consts，两个 1000 字面量也可能 is 相等，但那是编译优化不是语言保证。

判断类型用 `isinstance(obj, T)` 而非 `type(obj) is T`，因为前者承认子类：`isinstance(True, int)` 为 True，bool 正是 int 的子类。

```python
small_a = 100
small_b = 100
big_a = int('1000')
big_b = int('1000')
print('small_same', small_a is small_b)
print('big_same', big_a is big_b)
print('values_equal', big_a == big_b)
print('bool_is_int', isinstance(True, int), True + True)
print('type_ok', type(small_a) is int)
```

<OutputBox title='主示例运行结果' output='small_same True\nbig_same False\nvalues_equal True\nbool_is_int True 2\ntype_ok True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='small_a = 100\nsmall_b = 100\nbig_a = int(&#39;1000&#39;)\nbig_b = int(&#39;1000&#39;)\nprint(&#39;small_same&#39;, small_a is small_b)\nprint(&#39;big_same&#39;, big_a is big_b)\nprint(&#39;values_equal&#39;, big_a == big_b)\nprint(&#39;bool_is_int&#39;, isinstance(True, int), True + True)\nprint(&#39;type_ok&#39;, type(small_a) is int)' :notes='["把名字 small_a 绑定到整数 100，落在 -5..256 缓存池内", "第二个名字绑定同值，命中同一个缓存的单例对象", "用运行时构造绕开字面量合并，得到一个新的大整数对象", "再次构造，得到另一个独立的大整数对象", "is 比较身份：两个 100 都指向缓存单例，故为 True", "is 比较身份：两次 int() 各建对象，故为 False", "== 比较值，两个 1000 值相等，故为 True", "bool 是 int 子类，isinstance 为真；True + True 得整数 2", "type 返回 int，用 is 比较单例类型对象成立"]' title='第 006 讲 · 一切皆对象：id、type、value 与可变性' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**对象三要素与判断方式**

| 要素 | 读法 | 比较手段 | 典型误用 |
| --- | --- | --- | --- |
| 身份 identity | id(obj) | is / is not | 用 is 比较数值大小 |
| 类型 type | type(obj) | isinstance(obj, T) | 用 type(x) is T 忽略子类 |
| 值 value | 对象自身数据 | == 调用 __eq__ | 自定义类不实现 __eq__ 时退化成比身份 |


## 可变与不可变：同一份赋值，两种结果

对象按值能否原地改变分成两类。不可变的有 int、float、str、bytes、tuple、frozenset、bool，所谓「改变」其实是让名字重新绑定到新对象，因此 `n += 1` 对 int 会算出新对象再赋值，`id(n)` 随之变化。

可变的有 list、dict、set、bytearray 以及大多数自定义类实例，它们有原地修改的方法（append、`__setitem__`、add），对象身份不变、内容改变，于是所有绑定到它的名字都会看到变化。

这正是别名穿透的来源：`x = y = []` 让两个名字指向同一个 list，`x.append(1)` 之后 y 也是 [1]；函数传参传的是对象引用，被调用方对可变参数原地修改会穿透到调用方，接口设计时必须显式约定「是否会被修改」，必要时传副本或转成 tuple。

增强赋值 += 在两类对象上行为不同，是因为它先尝试 `__iadd__`（原地协议），不可变类型没有该协议才退回 `__add__` 加重新绑定：`list += [x]` 原地扩、id 不变，`int += 1` 重新绑定、id 改变。

用 `id()` 前后对比、或用 `sys.getrefcount` 观察引用数，都能把这条差别变成可测量的证据。

边界信号很明确：明明没赋值却看到数据变了，一定是某个可变对象被多个名字共享。

```python
n = 1
id_before = id(n)
n += 1
print('int_rebound', id(n) != id_before)

lst = [1]
lst_id = id(lst)
lst += [2]
print('list_inplace', id(lst) == lst_id)
print('list_value', lst)
```

<OutputBox title='对照写法：先自己猜，再点开' output='int_rebound True\nlist_inplace True\nlist_value [1, 2]' guess="true" />


## 小整数缓存、驻留与引用计数：sys 里的证据

CPython 把 -5 到 256 的整数做成预分配的单例池，赋值这个范围内的整数不会新建对象，而是直接复用池里的实例，目的是让小整数的频繁创建与比较更省；这个范围是实现细节，不要写进业务判断。

字符串驻留则把符合标识符规则或短的字符串放进全局字典复用，`sys.intern(s)` 可手动驻留以加速大量重复键的比较，但跨进程、跨版本行为不同。同一编译单元里编译器还会把重复字面量合并到 co_consts，造成「两个 1000 字面量 is 相等」的假象；

用运行时构造（`int('1000')`、字符串拼接）绕开常量合并，才能看清真实的对象创建行为。

`sys.getrefcount(obj)` 返回对象当前引用数，比实际多 1，因为参数本身临时持有一个引用，能看到共享之后计数上升；

`sys.getsizeof(obj)` 返回对象自身占用的字节数，空 list 与含三元素的 list 大小不同，说明容器存的是引用、随元素增长。

还要注意 `id()` 在对象被回收后可能被新对象复用，所以「保存 id 以后再比较」也不可靠，比较应在同一生命周期内完成。把 is、id、getrefcount、getsizeof 一起用，才能把「变量是标签」从比喻变成可核对的事实。


## PyObject 与引用计数：别名为什么会穿透

CPython 里所有值都是堆上的 PyObject，结构体头部固定含 `ob_refcnt`（引用计数）与 `ob_type`（类型指针），具体值放在类型专属的后续字段里。变量名不占对象空间，它们存在名字空间字典（globals、locals、实例 `__dict__`）中，赋值就是把键指向某个 PyObject 指针。

is 直接比较两个指针是否相等，因此不受 `__eq__` 影响；== 则通过类型的方法表找到 `__eq__` 做值比较，可被重载，这也是 NumPy 数组之间 == 返回数组而非布尔的原因。

引用计数让对象在最后一个引用消失时立即回收，而 `x = y = obj` 会把 `ob_refcnt` 加两次，`sys.getrefcount` 能读到这个变化（含参数临时引用）。

小整数池在实现里是预分配的数组，启动时建好 -5 到 256，赋值命中范围就返回池内单例；字符串驻留则维护一张全局字典。list 结构体里只存一个 PyObject 指针数组，append 改的是数组元素，对象头与地址不变——这就是可变对象「原地改」与不可变对象「重新绑定」在内存层面的分界。

id 复用、对象池、驻留都属于实现优化，语言只保证同一对象身份相等，不保证值相等的对象身份相同。

<ConceptDiagram type='flow4' title='第 006 讲 · 对象三要素与 is / == 的分工' labels='对象三要素与 is / == 的分工|可变与不可变：同一份赋值，两种结果|小整数缓存、驻留与引用计数：sys 里的证据' caption='建立 Python 对象模型的第一张心智图' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 别名穿透审计：定位可变默认参数造成的串数据

一个配置服务把默认标签列表写在函数签名里，不同请求之间的标签会互相串，日志里看到某次请求凭空多了上一次加的标签。根因不是并发，而是可变默认参数在 def 执行时创建一次、被所有调用共享。

下面这段实现一个审计器：用 `id` 与 `sys.getrefcount` 检测两个名字是否指向同一对象，演示 append 如何穿透到别名，再给出以 None 占位、进入函数才新建列表的正确写法，并断言两次调用互不污染。

真实项目还应把「参数是否会被修改」写进文档，对外部传入的可变对象先复制再处理，避免调用方拿到被悄悄改过的数据。

```python
import sys

def audit(a, b):
    return {'same_object': a is b,
            'refcount_ge': sys.getrefcount(a) >= 3,
            'value_equal': a == b}

shared = []
alias = shared
print('before', audit(shared, alias))
shared.append('tag')
print('after_alias', alias)

def bad_add(tag, bucket=[]):
    bucket.append(tag)
    return bucket

def good_add(tag, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(tag)
    return bucket

b1, b2 = bad_add('a'), bad_add('b')
g1, g2 = good_add('a'), good_add('b')
print('bad_shared', b1 is b2)
print('good_isolated', g1 is not g2)
print('good_values', g1, g2)
```

<Callout type="idea" title='落地提示' text='函数传参一律传对象引用，可变对象在被调用方原地修改会穿透到调用方，接口设计时要显式约定' />


## 身份判断错因与对象速记

<Exercise title='基础：区分 is 与 ==' task='给 100 绑定两个名字，分别打印 a is b、int(&#39;1000&#39;) is int(&#39;1000&#39;)、1000 == int(&#39;1000&#39;)，并解释第二个为什么是 False。' solution='a = 100\nb = 100\nprint(&#39;small&#39;, a is b)\nprint(&#39;big&#39;, int(&#39;1000&#39;) is int(&#39;1000&#39;))\nprint(&#39;equal&#39;, 1000 == int(&#39;1000&#39;))' explain='100 命中缓存池，两个名字指向同一单例；1000 超出池且由运行时构造，两次新建对象身份不同；== 只比值所以为 True。' />

<Exercise title='进阶：用 id 证明 += 的两条路径' task='分别观测 list 与 int 执行 += 前后 id 是否改变，打印两个布尔，并说明 __iadd__ 与 __add__ 的差别。' solution='n = 1\ni0 = id(n)\nn += 1\nlst = [1]\nl0 = id(lst)\nlst += [2]\nprint(&#39;int_id_changed&#39;, id(n) != i0)\nprint(&#39;list_id_same&#39;, id(lst) == l0)' explain='list 实现 __iadd__ 原地扩展、身份不变；int 不可变，+= 退回 __add__ 算出新对象再重新绑定，故 id 改变。' />

<Quiz no='006-1' q='关于 is 与 ==，哪项描述准确？' :options='["is 比较身份（指针），== 比较值并调用 __eq__；is 只该用于 None 等单例", "is 是更严格的 ==，可用来比较整数", "== 比较内存地址", "两者完全等价"]' answer="0" explain='is 不做值比较也不受 __eq__ 影响，身份由对象地址决定；None、True、False 等是全局单例，用 is 判断才可靠。' />

<Quiz no='006-2' q='int(&#39;1000&#39;) is int(&#39;1000&#39;) 的结果是？' :options='["False，两次运行时构造各新建大整数对象", "True，整数都来自小整数池", "True，1000 会被驻留", "取决于 sys.intern 是否调用"]' answer="0" explain='1000 超出 -5..256 缓存范围，且 int(&#39;1000&#39;) 是运行时调用而非编译期字面量，不会被合并进 co_consts，因此是两个对象。' />

<Quiz no='006-3' q='list 的 += 为什么不会改变 id？' :options='["list 实现了 __iadd__ 原地扩展，对象身份不变", "因为 list 不可变", "编译器做了常量折叠", "id() 对 list 不生效"]' answer="0" explain='增强赋值优先查 nb_inplace_add 槽位，list 提供 __iadd__ 直接改 ob_item 数组，返回自身；不可变类型才退回加法重新绑定。' />

<Predict no='006-4' q='主示例里 print(&#39;big_same&#39;, big_a is big_b) 输出什么？（big_a = int(&#39;1000&#39;), big_b = int(&#39;1000&#39;)）' :options='["big_same False", "big_same True", "抛出 TypeError"]' answer='0' output='big_same False' explain='两次 int(&#39;1000&#39;) 在运行时各新建 PyLongObject，1000 超出 -5..256 缓存池，也不是编译器合并的字面量，因此身份不同；但两者值相等，== 为 True。' />

<FillBlank no='006-5' tpl='print(&#39;small_same&#39;, small_a ___ small_b)' :answers='["is"]' hint='回想本讲关于 对象的三要素 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 对象三要素与 is / == 的分工 的落点。' />

<KnowledgeCard :points='["对象三要素：身份 id()（进程内唯一）、类型 type()（不变）、值（可变对象可原地改）", "is 比较身份、== 比较值（调用 __eq__）；is 只用于 None / True / False / Ellipsis 等单例", "CPython 缓存 -5 到 256 的整数并驻留部分字符串；同编译单元的重复字面量还会被合并进 co_consts", "不可变对象 += 走 __add__ 重新绑定（id 变），可变对象走 __iadd__ 原地改（id 不变）", "函数传参传引用，可变对象原地修改穿透到调用方；默认参数用 None 占位再新建", "sys.getrefcount 含参数临时引用（比实际多 1），sys.getsizeof 反映容器存引用而非值本身"]' :pitfalls='["用 is 比较整数或字符串的值", "把可变对象当默认参数或共享给多个名字", "认为 += 对所有类型都是原位修改", "用 is 比较值、用 == 比较身份是最典型的误用；is 只该用来判断 None、True、False 这类单例"]' summary='变量不是装值的盒子，而是贴在对象上的标签；理解这一点，后面所有关于别名、拷贝、参数传递的疑惑都会消失' />

1. 对象三要素：身份 id()（进程内唯一）、类型 type()（不变）、值（可变对象可原地改）

2. is 比较身份、== 比较值（调用 __eq__）；is 只用于 None / True / False / Ellipsis 等单例

3. CPython 缓存 -5 到 256 的整数并驻留部分字符串；同编译单元的重复字面量还会被合并进 co_consts

[下一讲：变量是名字绑定：赋值、引用与命名规范](/foundation/variables)
