---
title: 第 028 讲 · 函数定义与参数形态
description: 准确使用五种参数并设计稳定接口
---

<StageHeader stage='L3 · 函数与抽象' level='★☆☆☆☆' time='30 分钟' goal='准确使用五种参数并设计稳定接口' prereq='第 027 讲 · 阶段综合：词频统计与内存版 KV' />

# 第 028 讲 · 函数定义与参数形态

上一讲把词频统计收成了能测的小工具，那些重复步骤其实在等更省心的组织方式。从这里进入函数与抽象，先安顿一段逻辑怎样被稳妥调用：一个跑了半年的分页查询，想给内部参数换个名字，却发现几千处调用有一部分写死了旧名；带默认字典的函数，两次无关请求还悄悄串了数据。

我们先把位置、关键字、可变与仅关键字几种参数摆开，看清 / 和 * 怎样切分签名；再看默认值在函数定义那刻就定下来；最后借签名工具读一份绑定契约。需要变量、容器和最简单的函数；走完你能设计出加参数、改名字都不惊动调用方的接口。


## 改个内部参数名，几千处调用怎么就崩了

一个分页接口的封装函数上线半年后要加超时参数：原签名是 `query(page, size)`，几千处调用都写成 `query(1, 20)`。

库作者想把内部参数名从 size 重命名为 limit，结果所有写成 `query(page=1, size=20)` 的调用全崩。

更隐蔽的坑在默认值：def `query(page, size, filters={})` 看着人畜无害，两次调用却共享同一个字典，第一次请求加进去的过滤条件悄悄出现在第二次请求里，线上表现为偶发串单。

朴素解法是把可选配置全塞进 **kwargs，或干脆让调用方传一个 dict：前者让签名失去自文档性、IDE 无法补全、拼错的参数名要运行到深处才报 TypeError，后者把必填项与类型全变成口头约定。

本讲用 / 与 * 把参数切成三段、用 `inspect.signature` 读出真实的绑定契约，把重命名兼容、可变默认值、参数校验这三类问题一次解决。


## 五段式参数：斜杠与星号如何切分签名

Python 的参数按定义顺序分成五段：仅位置、位置或关键字、可变位置 *args、仅关键字、可变关键字 **kwargs。

语法上 / 之前的参数只能按位置传，裸 * 或 *args 之后的参数只能按关键字传，两段之间两者皆可，完整骨架是 def `f(a, b, /, c, d=1, *args, e, f=2, **kw)`。

仅位置参数由 PEP 570 在 3.8 引入，动机有两个：库作者可以重命名参数而不破坏按位置调用的旧代码；pow、divmod、len 这类 C 实现的内建函数历史上不接受关键字，纯 Python 函数要表达同样约束必须靠 /。

仅关键字参数由 PEP 3102 在 3.0 引入，它强制调用处写出配置名，既自文档化，又让以后在中间插入新参数不会打乱位置顺序。

`inspect.Parameter.kind` 恰好有五个枚举值 POSITIONAL_ONLY、POSITIONAL_OR_KEYWORD、VAR_POSITIONAL、KEYWORD_ONLY、VAR_KEYWORD，`signature(f)`.parameters 是按定义顺序排列的映射，每个元素还带 default 与 annotation。

编译期写进 code object 的 co_argcount 统计位置参数（含仅位置）、co_posonlyargcount 统计仅位置个数、co_kwonlyargcount 统计仅关键字个数，这些都是整数常量，运行时不变。公开 API 把可选配置放成仅关键字，是维护兼容性的关键手段。

```python
import inspect

def connect(host, port, /, timeout=1.0, *, retries=3, **options):
    return (host, port, timeout, retries, options)

sig = inspect.signature(connect)
print(connect('db.local', 5432, 2.0, retries=5, ssl=True))
for name, p in sig.parameters.items():
    default = 'no-default' if p.default is inspect.Parameter.empty else repr(p.default)
    print(name, p.kind.name, default)
```

<OutputBox title='主示例运行结果' output='(&#39;db.local&#39;, 5432, 2.0, 5, {&#39;ssl&#39;: True})\nhost POSITIONAL_ONLY no-default\nport POSITIONAL_ONLY no-default\ntimeout POSITIONAL_OR_KEYWORD 1.0\nretries KEYWORD_ONLY 3\noptions VAR_KEYWORD no-default' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import inspect\n\ndef connect(host, port, /, timeout=1.0, *, retries=3, **options):\n    return (host, port, timeout, retries, options)\n\nsig = inspect.signature(connect)\nprint(connect(&#39;db.local&#39;, 5432, 2.0, retries=5, ssl=True))\nfor name, p in sig.parameters.items():\n    default = &#39;no-default&#39; if p.default is inspect.Parameter.empty else repr(p.default)\n    print(name, p.kind.name, default)' :notes='["导入 inspect：signature 与 Parameter 是读取参数契约的官方接口", "用 / 把 host、port 定为仅位置；用 * 把 retries 及之后定为仅关键字", "把五种形态收到的值打包成元组返回，便于逐项核对绑定结果", "取得 Signature 对象，parameters 是按定义顺序排列的映射", "2.0 按位置给 timeout，retries=5 走仅关键字，ssl=True 落进 **options", "遍历每个 Parameter，准备读取名字、kind 与默认值", "无默认值的参数其 default 是哨兵 inspect.Parameter.empty，转成可读串", "打印名字、kind.name 与默认值，得到完整的参数契约表"]' title='第 028 讲 · 函数定义与参数形态' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**五种参数形态与默认值存放处**

| 形态 | 语法 | inspect.Parameter.kind | 默认值存放处 | 传参方式 |
| --- | --- | --- | --- | --- |
| 仅位置 | / 之前 | POSITIONAL_ONLY | __defaults__ 对应槽位 | 只能按位置 |
| 位置或关键字 | / 与 * 之间（默认形态） | POSITIONAL_OR_KEYWORD | __defaults__ 对应槽位 | 位置或关键字皆可 |
| 可变位置 | *args | VAR_POSITIONAL | 无固定默认值，调用时成元组 | 接收多余位置参数 |
| 仅关键字 | 裸 * 或 *args 之后 | KEYWORD_ONLY | __kwdefaults__ | 只能按关键字 |
| 可变关键字 | **kwargs | VAR_KEYWORD | 无固定默认值，调用时成字典 | 接收多余关键字参数 |

<ConceptDiagram type='hub4' title='第 028 讲 · 五段式参数：斜杠与星号如何切分签名' labels='五段式参数：斜杠与星号如何切分签名|默认值只在定义时求值一次|解包、绑定与一等对象' caption='准确使用五种参数并设计稳定接口' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 默认值只在定义时求值一次

def 是一条执行语句，解释器执行到它时才创建 function 对象；

默认值表达式就在这一刻求值，结果对象被存进 `function.__defaults__`（对应位置/位置或关键字参数，是一个元组）与 `function.__kwdefaults__`（对应仅关键字参数，是一个 dict），而不是每次调用重算。

因此默认值若是可变对象（空列表、空字典、空集合），所有调用共享的是同一个对象引用，任何原地修改都会累积到后续调用，这正是串单 bug 的根因。标准修复是默认 None、函数体内 if x is None: x = []，因为 None 是不可变单例，每次调用都会新建容器。

同类陷阱还有 def `f(t=time.time()`)：时间戳是导入那一刻，不是调用时刻；

默认值表达式若引用了尚未定义的名字，会在 def 执行时直接 NameError。可以用 `__defaults__` 与 `__kwdefaults__` 直接读出当前绑定，ruff 的 B006 规则会静态告警可变默认值。

还要区分没有默认值的情况：此时 `Parameter.default` 是哨兵对象 `inspect.Parameter.empty`，而不是 None，用它做判断才不会把显式的 None 默认值误判为缺失。

```python
def add(item, seen=[]):
    seen.append(item)
    return seen

print(add.__defaults__)
r1 = add('a')
r2 = add('b')
print(r1, r2, r1 is r2)
print(add.__defaults__)

def add2(item, seen=None):
    if seen is None:
        seen = []
    seen.append(item)
    return seen
print(add2('a'), add2('b'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='([],)\n[&#39;a&#39;, &#39;b&#39;] [&#39;a&#39;, &#39;b&#39;] True\n([&#39;a&#39;, &#39;b&#39;],)\n[&#39;a&#39;] [&#39;b&#39;]' guess="true" />


## def 是一次执行期构造：从 code object 到 __defaults__

def 语句在 CPython 里是一次对象构造：编译器先把函数体编译成独立的 code object，记录 co_argcount、co_posonlyargcount、co_kwonlyargcount、co_varnames 与 co_flags；

等模块执行到 def 这一行时，运行时才求值默认值表达式，用 MAKE_FUNCTION 指令把 code object、默认值元组、注解字典、闭包 cell 等打包成 PyFunctionObject 并绑定到名字。

默认值因此是 function 对象上的 `__defaults__` / `__kwdefaults__`，属于对象状态而非字节码常量，函数体 code object 的 co_consts 里并不包含默认值，只有函数体内用到的字面量。

调用发生时，解释器按 co_argcount 与 co_flags 把实参装进新帧的局部变量数组：位置参数按槽位落位，多余位置参数组装成元组给 *args，关键字参数按名匹配，多余者组装成字典给 **kwargs；这一绑定由 CALL 系列指令完成，匹配失败就抛 TypeError。

`inspect.signature` 之所以能还原契约，是因为它读的正是 function 对象与 code object 上这些编译期元数据，而不是解析源码文本。

理解 def 是执行期构造，才能解释为什么默认值只求值一次、为什么可变默认值会跨调用共享。


## 解包、绑定与一等对象

调用侧用 *seq 把可迭代展开成位置参数、**mapping 把映射展开成关键字参数，二者都发生在调用前；映射的键必须是 str，否则抛 TypeError: keywords must be strings；

同一个参数既由位置又由关键字给出时抛 TypeError: got multiple values for argument 'a'；位置专属参数被写成关键字则抛 got some positional-only arguments passed as keyword arguments。

`inspect.signature(f)`.`bind(*args, **kwargs)` 与 bind_partial 按签名规则做绑定，返回 BoundArguments，其 .arguments 是有序字典，`apply_defaults()` 能补上默认值，这是框架在真正调用前校验参数的正确工具，比手写 isinstance 可靠。

函数是一等对象：可赋值给变量、放进容器、作参数与返回值，携带 `__name__`、`__qualname__`、`__doc__`、`__annotations__`、`__module__`、`__defaults__`、`__code__` 等属性，函数名只是指向 function 对象的一个名字，改名后旧引用仍指向原对象。

def 与 lambda 生成的是同一种 function 类型，区别只在有无名字、能否包含语句。参数解包与绑定之所以能实现，依赖 code object 的 co_flags 里的 CO_VARARGS（0x04）与 CO_VARKEYWORDS（0x08）标记，以及 co_varnames 里参数与局部变量的排列。


## 参数语法、版本与绑定错误速查


## 给已发布的公共 API 做兼容性重构

一个数据 SDK 的 `query(page, size)` 已被数千处调用，现在要加 timeout、retries 两个可选配置，同时库作者想在未来把内部参数名换掉而不破坏旧代码。

做法是用 / 把 page、size 锁成仅位置：调用方只能按位置给，库内部重命名不影响任何人；新增配置全部放到裸 * 之后成为仅关键字参数，调用处自带说明、以后再插入新配置也不会打乱位置顺序；

再用 `inspect.signature.bind` 做一层前置校验，把参数错误挡在真正执行之前。

下面这段把这套约束写成一个 safe_call 包装：它先 bind、apply_defaults，再转发，并演示按关键字传仅位置参数会被当场拒绝。真实项目还应把 bind 失败记进日志，方便定位到底是哪个调用方写错了参数。

```python
import inspect

def query(page, size, /, *, timeout=1.0, retries=3):
    return {'page': page, 'size': size, 'timeout': timeout, 'retries': retries}

sig = inspect.signature(query)

def safe_call(*args, **kwargs):
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    return query(*bound.args, **bound.kwargs)

print(safe_call(1, 20))
print(safe_call(1, 20, timeout=2.5))
try:
    safe_call(1, size=20)
except TypeError as e:
    print(type(e).__name__, str(e))
```

<Callout type="idea" title='落地提示' text='公开 API 优先用仅关键字参数表达可选配置，调用处自带说明，后续加参数不会打乱位置顺序' />


## 参数契约的练习与速记

<Exercise title='基础：读出五种参数形态' task='定义 def f(a, b=2, /, c=3, *args, d, e=5, **kw)，用 inspect.signature 逐个打印参数名、kind.name 与默认值，指出哪些默认值落在 __defaults__、哪些落在 __kwdefaults__。' solution='import inspect\n\ndef f(a, b=2, /, c=3, *args, d, e=5, **kw):\n    return a\n\nfor name, p in inspect.signature(f).parameters.items():\n    default = &#39;empty&#39; if p.default is inspect.Parameter.empty else repr(p.default)\n    print(name, p.kind.name, default)' explain='a 与 b 是 POSITIONAL_ONLY，c 是 POSITIONAL_OR_KEYWORD，args 是 VAR_POSITIONAL，d 与 e 是 KEYWORD_ONLY，kw 是 VAR_KEYWORD；b、c 的默认值进 __defaults__，d、e 的默认值进 __kwdefaults__。' />

<Exercise title='进阶：用 bind 在调用前拦截参数错误' task='实现 safe_div(a, b, /, *, ndigits=None)，用 inspect.signature 事先 bind 几组错误实参，打印异常类型与消息，说明为什么 bind 比直接调用更适合做参数校验。' solution='import inspect\n\ndef safe_div(a, b, /, *, ndigits=None):\n    r = a / b\n    return r if ndigits is None else round(r, ndigits)\n\nsig = inspect.signature(safe_div)\nprint(safe_div(1, 3, ndigits=2))\nfor bad in ((1, 3, 4), (1,)):\n    try:\n        sig.bind(*bad)\n    except TypeError as e:\n        print(type(e).__name__, str(e))' explain='bind 只按签名做绑定、不执行函数体，能在触发副作用之前发现参数个数、仅位置/仅关键字形态错误；apply_defaults 还能补齐默认值用于审计。' />

<Predict no='028-P' q='对 def f(a, b=1, *, c=2, **kw) 执行 inspect.signature(f).bind(9, c=7, x=1).arguments 得到什么？' :options='["{&#39;a&#39;: 9, &#39;c&#39;: 7, &#39;kw&#39;: {&#39;x&#39;: 1}}", "{&#39;a&#39;: 9, &#39;b&#39;: 1, &#39;c&#39;: 7, &#39;kw&#39;: {&#39;x&#39;: 1}}", "抛 TypeError，因为 b 没传"]' answer='0' output='{&#39;a&#39;: 9, &#39;c&#39;: 7, &#39;kw&#39;: {&#39;x&#39;: 1}}' explain='bind 只绑定显式传入的实参，不自动补默认值；要补齐需再调 apply_defaults()。b 没传就不出现在 arguments 里，x 落进 **kw。' />

<Quiz no='028-1' q='关于默认值求值时机，下面哪一项是准确的？' :options='["默认值在 def 执行时求值一次，结果存进 __defaults__ / __kwdefaults__", "默认值每次调用都重新求值", "默认值存在函数体 code object 的 co_consts 里", "可变默认值会被解释器自动深拷贝"]' answer="0" explain='def 是执行语句，执行到才求值并写入 function 对象；co_consts 只放函数体字面量；可变默认值不会拷贝，这正是跨调用串数据的根因。' />

<Quiz no='028-2' q='def f(a, /, b, *, c) 的调用，下面哪一个是合法的？' :options='["f(1, 2, c=3)", "f(a=1, b=2, c=3)", "f(1, b=2, 3)", "f(1, 2, 3)"]' answer="0" explain='a 仅位置只能按位置传；b 位置或关键字皆可；c 仅关键字必须写名字；位置参数不允许出现在关键字参数之后。' />

<Quiz no='028-3' q='要把公共 API 的可选配置改造成向后兼容且以后能安全加参数，应选？' :options='["把配置放成裸 * 之后的仅关键字参数并给默认值", "全部塞进 **kwargs", "要求调用方改传一个 dict", "把配置都改成位置参数"]' answer="0" explain='仅关键字让调用处写出名字、以后插入新参数不打乱位置顺序；**kwargs 会丢掉签名信息、类型与静态校验，dict 让必填项变成口头约定。' />

<KnowledgeCard :points='["/ 之前仅位置（PEP 570，3.8+）；裸 * 或 *args 之后仅关键字（PEP 3102，3.0+）", "默认值在 def 执行时求值一次，存 __defaults__(元组) 与 __kwdefaults__(dict)；co_consts 里没有默认值", "可变默认值用 None 哨兵修复：if x is None: x = []", "inspect.Parameter.kind 五种：POSITIONAL_ONLY / POSITIONAL_OR_KEYWORD / VAR_POSITIONAL / KEYWORD_ONLY / VAR_KEYWORD", "signature(f).bind(*a, **k) 只绑定显式实参，apply_defaults() 才补默认值；无默认值时 default 是 inspect.Parameter.empty", "co_flags 里 CO_VARARGS=0x04、CO_VARKEYWORDS=0x08 标记是否收 *args / **kwargs；** 解包的键必须是 str"]' :pitfalls='["默认值用空列表或空字典，数据跨调用串味", "给仅位置参数传关键字，线上偶发 TypeError", "把可选配置全塞进 **kwargs 导致拼错名字不报错", "默认值在函数定义时求值一次，若默认是可变对象，所有调用会共享同一份状态"]' summary='用 / 与 * 把参数切成三段，可以在不破坏调用方的前提下重命名内部参数，是库作者维护兼容性的关键手段' />

1. / 之前仅位置（PEP 570，3.8+）；裸 * 或 *args 之后仅关键字（PEP 3102，3.0+）

2. 默认值在 def 执行时求值一次，存 __defaults__(元组) 与 __kwdefaults__(dict)；co_consts 里没有默认值

3. 可变默认值用 None 哨兵修复：if x is None: x = []

[下一讲：返回值、None 与多返回值](/functions/returns)

<FillBlank no='028-F' tpl='___ inspect' :answers='["import"]' hint='回想本讲关于 位置与关键字参数 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 五段式参数：斜杠与星号如何切分签名 的落点。' />
