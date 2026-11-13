---
title: 第 040 讲 · 访问控制、property 与描述符协议
description: 掌握属性访问的底层协议
---

<StageHeader stage='L4 · 面向对象' level='★★★★☆' time='40 分钟' goal='掌握属性访问的底层协议' prereq='第 039 讲 · 属性查找、MRO 与 super' />

# 第 040 讲 · 访问控制、property 与描述符协议

> 描述符是 Python 里最被低估的机制：property、method、classmethod、staticmethod 全部由它实现，实例属性查找优先级也由它决定。本讲的目标是「掌握属性访问的底层协议」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P040' title="本讲目标" :items='["能说清名称改写与私有约定", "能说清property 的 getter / setter", "能说清数据描述符与非数据描述符", "能说清__get__ / __set__ / __delete__", "能说清优先级规则"]' />

## 1. 先建立直觉

**名称改写与私有约定**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**property 的 getter / setter**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**数据描述符与非数据描述符**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

<ConceptDiagram type='flow3' title='第 040 讲 · 名称改写与私有约定' labels='名称改写与私有约定|property 的 getter / setter|数据描述符与非数据描述符|__get__ / __set__ / __delete__' caption='掌握属性访问的底层协议' />

上图用本讲的三个核心概念标出了主线：**名称改写与私有约定 → property 的 getter / setter → 数据描述符与非数据描述符**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 名称改写与私有约定 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 3", "tone": "green"}, {"title": "深入边界", "desc": "厘清 property 的 getter / setter 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 __set_name__ 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**名称改写与私有约定**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

```python
class Positive:
    def __set_name__(self, owner, name):
        self.name = name
    def __get__(self, obj, owner=None):
        return obj.__dict__.get(self.name, 0)
    def __set__(self, obj, value):
        if value < 0: raise ValueError("must be positive")
        obj.__dict__[self.name] = value

class Order:
    qty = Positive()

o = Order(); o.qty = 3
print(o.qty)
```

<OutputBox title="运行结果" output='3' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError("must be positive")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)' :notes='["实现 __set__ 即为数据描述符，优先级高于实例字典", "__set_name__ 在类创建时拿到字段名", "校验集中在一处，所有赋值路径都受约束", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 040 讲 · 访问控制、property 与描述符协议' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**property 的 getter / setter**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
class Vector:
    def __init__(self, x, y): self.x, self.y = x, y
    def __len__(self): return 2
    def __repr__(self): return f"V({self.x},{self.y})"

v = Vector(1, 2)
print(len(v), bool(v), v)
```

<OutputBox title="对照写法的输出（先自己猜）" output='2 True V(1,2)' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError(\"must be positive\")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f\"V({self.x},{self.y})\"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才能保」' />

## 3. 深入一步：规则与边界

**数据描述符与非数据描述符**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**__get__ / __set__ / __delete__**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**优先级规则**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 名称改写与私有约定 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才 |
| property 的 getter / setter | 这里的关键词是「什么时候」和「代价是什么」 | 把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才 |
| 数据描述符与非数据描述符 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才 |
| __get__ / __set__ / __delete__ | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才 |
| 优先级规则 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才 |

<Term word='名称改写与私有约定' text='描述符是 Python 里最被低估的机制：property、method、classmethod、staticmethod 全部由它实现，实例属性查找优先级也由它决定' />

<Callout type="warn" title="易错点" text='把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才能保证每次赋值都经过同一入口' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：名称改写与私有约定", "body": "**名称改写与私有约定**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：property 的 getter / setter", "body": "**property 的 getter / setter**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：数据描述符与非数据描述符", "body": "**数据描述符与非数据描述符**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：__get__ / __set__ / __delete__", "body": "**__get__ / __set__ / __delete__**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<ArchBlueprint title='第 040 讲 · 分层视角' caption='把「名称改写与私有约定」放进系统分层里看' :layers='[{"name": "入口层", "note": "请求与使用方式", "protocol": "函数调用 / HTTP", "items": [{"label": "名称改写与私有约定", "sub": "对外接口", "detail": "**名称改写与私有约定**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tone": "blue"}]}, {"name": "逻辑层", "note": "规则、状态与校验", "protocol": "Python 对象协议", "items": [{"label": "property 的 g", "sub": "核心处理", "detail": "**property 的 getter / setter**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而", "tone": "purple"}]}, {"name": "资源层", "note": "数据、IO 与失败处理", "items": [{"label": "__set_name__", "sub": "落地与收尾", "detail": "ORM 字段、配置校验、懒加载属性、类型约束都适合用描述符实现，一处定义全局生效", "tone": "green"}]}]' />

## 4. 工程实践

ORM 字段、配置校验、懒加载属性、类型约束都适合用描述符实现，一处定义全局生效 **__set_name__**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **名称改写与私有约定** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「__set_name__」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「__set_name__」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 名称改写与私有约定 与 __set_name__ 两个关注点，并说明你的取舍。' :hints='["回到 名称改写与私有约定 的规则", "留意易错点：把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才能保证每次赋", "先让代码跑通，再补边界与异常分支"]' solution='class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f"V({self.x},{self.y})"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；ORM 字段、配置校验、懒加载属性、类型约束都适合用描述符实现，一处定义全局生效' />

## 随堂检测

<Quiz no='040-1' q='在本讲讨论的「名称改写与私有约定」语境下，下面哪一种说法是准确的？' :options='["描述符是 Python 里最被低估的机制：property、method、classmethod、staticmethod 全部由它实现，实例属性查找优先级", "名称改写与私有约定 只影响代码的书写形式，不会改变任何运行时行为", "名称改写与私有约定 在所有 Python 实现与所有版本中表现完全一致", "只要用了 名称改写与私有约定，就不必再考虑 __set_name__ 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 __set_name__ 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='040-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["3", "3\n（无更多输出）", "AttributeError: 名称改写与私有约定 不可用"]' answer="0" output='3' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='040-3' tpl='    _____set_name__(self, owner, name):' :answers='["def"]' hint='回想本讲关于 名称改写与私有约定 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["名称改写与私有约定：名称改写与私有约定", "property 的 getter / setter：property 的 getter / setter", "数据描述符与非数据描述符：数据描述符与非数据描述符", "__get__ / __set__ / __delete__：__get__ / __set__ / __delete__"]' :pitfalls='["把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才能保证每次赋值都经过同一入口", "忽略版本差异，把 __set_name__ 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：描述符是 Python 里最被低估的机制：property、method、classmethod、staticmethod 全部由它实现，实例属性查找优先级也由它决定' />

## 小结与下一讲

1. 名称改写与私有约定：名称改写与私有约定
2. property 的 getter / setter：property 的 getter / setter
3. ORM 字段、配置校验、懒加载属性、类型约束都适合用描述符实现，一处定义全局生效

[下一讲：特殊方法：repr、比较、算术与容器协议](/oop/special-methods)
