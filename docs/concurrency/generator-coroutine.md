---
title: 第 067 讲 · 生成器协程：send、yield from 与调度器
description: 从语言机制推出 async/await 的由来
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='40 分钟' goal='从语言机制推出 async/await 的由来' prereq='第 066 讲 · IO 多路复用：select / poll / epoll' />

# 第 067 讲 · 生成器协程：send、yield from 与调度器

上一讲把事件循环在系统调用层的样子摊开：一个线程盯住一批连接，谁就绪就回调谁。回调一多，一个边等 IO 边往下走的任务会被拆成散落的函数，恢复点藏在各处，读起来绕成一团。其实语言本身早给了更省力的东西——生成器天生带暂停点，能停住，再被推着走。把这几个暂停点交给一个调度器，协程的雏形就出来了。

这一讲先看 `send` 怎么让生成器双向通信，再用 `yield from` 把暂停点委托给子生成器，接着亲手写一个最小调度器让几个任务轮转起来，最后沿 PEP 342、380、492 这条线看清 async/await 的来历，并和回调写法比一比。需要你熟悉生成器、`yield` 与事件循环的概念；学完能从语言机制推出这套语法，也读得懂 asyncio 里 Future 与 Task 各管什么。


## 读 asyncio 源码卡在 Future 与 Task 的分工

读 asyncio 源码时，很多人卡在同一处：为什么 `await` 一个协程不会执行、为什么生成器里 `return` 的值要从 `StopIteration.value` 取、为什么 PEP 492 又另造出 async/await。

自己动手写调度器，第一次就写 `gen.send(5)`，得到 can't send non-None value to a just-started generator——刚创建的生成器还没停在暂停点，送非 None 值进去没有落点。

还有人在生成器里 `raise StopIteration` 想结束循环，3.7 之后却被转成 RuntimeError: generator raised StopIteration，日志里完全对不上。

更常见的是把 `yield from` 当成「遍历另一个可迭代对象」，没注意到它还会透明转发 `send`、`throw`、`close`，并把子生成器的 `return` 值作为表达式结果。

这几件事不是零散的语法细节，而是同一条演进线：PEP 342 让生成器能双向通信，PEP 380 加委托，PEP 492 把「暂停点用于 IO 等待」固化成原生协程。走完这条线，asyncio 里 Future/Task 的分工与那些历史包袱才有解释。

<Callout type="warn" title='先看一个真实会出错的写法' text='第一次就 gen.send(5) 驱动生成器：生成器尚未启动到第一个 yield，没有表达式可接收值' />


## 生成器状态机：send、throw 与 close

包含 `yield` 的函数是生成器函数，调用它只返回生成器对象、一行都不执行。

首次必须用 `next(gen)` 或 `gen.send(None)` 启动到第一个 `yield`，否则直接 `gen.send(5)` 会抛 TypeError，提示 can't send non-None value to a just-started generator。

`gen.send(value)` 恢复执行，把 value 作为当前 `yield` 表达式的值，并推进到下一个 `yield` 把新值交还；`gen.throw(exc)` 在暂停点抛异常，可被生成器内的 `try`/`except` 接住后继续 yield；`gen.close()` 在暂停点抛 `GeneratorExit`，生成器若此时又 yield 会触发 RuntimeError: generator ignored GeneratorExit。

`inspect.getgeneratorstate(gen)` 返回四种状态 `GEN_CREATED`、`GEN_RUNNING`、`GEN_SUSPENDED`、`GEN_CLOSED`。

生成器里 `return value`（3.3 起，PEP 380）等价于把值挂到 `StopIteration.value` 上；PEP 479 自 3.7 起默认生效（3.5 与 3.6 要显式启用 `generator_stop` 这个 future 特性），把漏出生成器的 StopIteration 转成 RuntimeError，免得它被 for 循环悄悄当成正常终止。

**生成器协议方法与状态**

| 方法 / 状态 | 作用 | 边界 / 报错 |
| --- | --- | --- |
| next(gen) / send(None) | 启动或推进到下一个 yield | 首次 send 非 None 抛 TypeError |
| gen.send(value) | 把 value 作为当前 yield 表达式的值 | 生成器已 CLOSED 则抛 StopIteration |
| gen.throw(exc) | 在暂停点抛异常，可被内部 except 接住 | 未捕获则向上传播 |
| gen.close() | 在暂停点抛 GeneratorExit | 若此时再 yield 触发 RuntimeError: generator ignored GeneratorExit |
| GEN_CREATED/SUSPENDED/CLOSED | getgeneratorstate 的四种状态之一（另有 RUNNING） | CLOSED 后不可再 send |

<Callout type="tip" title='核心心智模型' text='包含 `yield` 的函数是生成器函数，调用它只返回生成器对象、一行都不执行。首次必须用 `next(gen)` 或 `gen.send(None)` 启动到第一个 `yield`，否则直接 `gen.send(5)` 会抛 TypeError，提示 can&#39;t send non-None val…' />


## 对照：第一次就 send(5) 为什么报错

```python
def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            return total
        total += value

acc = accumulator()
print('prime', next(acc))
print('send 10', acc.send(10))
print('send 5', acc.send(5))
try:
    acc.send(None)
except StopIteration as e:
    print('return value', e.value)
```

<OutputBox title='主示例运行结果' output='prime 0\nsend 10 10\nsend 5 15\nreturn value 15' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def accumulator():\n    total = 0\n    while True:\n        value = yield total\n        if value is None:\n            return total\n        total += value\n\nacc = accumulator()\nprint(&#39;prime&#39;, next(acc))\nprint(&#39;send 10&#39;, acc.send(10))\nprint(&#39;send 5&#39;, acc.send(5))\ntry:\n    acc.send(None)\nexcept StopIteration as e:\n    print(&#39;return value&#39;, e.value)' :notes='["定义生成器函数，含 yield 故调用时不执行", "累加器初值为 0", "无限循环，暂停点就是 yield total", "value 接住 send 的值，同时产出当前 total", "约定 send(None) 表示结束", "return 把 total 挂到 StopIteration.value", "否则累加后回到循环顶部再次 yield", "空行，只用于分隔逻辑块，不影响执行结果。", "调用生成器函数只得到生成器对象", "首次必须 next 或 send(None) 启动", "send(10) 使 value=10，yield 出 10", "send(5) 后 total=15，yield 出 15", "准备捕获结束信号", "发送 None 触发 return", "return 以 StopIteration 形式冒出", "从 e.value 取回 return 值 15"]' title='第 067 讲 · 生成器协程：send、yield from 与调度器' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
def sub():
    v = yield 'sub-ready'
    return v * 2

def delegator():
    result = yield from sub()
    yield 'result:' + str(result)

d = delegator()
print('first', next(d))
print('delegated', d.send(21))
try:
    d.send(None)
except StopIteration as e:
    print('delegator done', e.value)

def guarded():
    try:
        yield 1
    except ValueError as e:
        yield 'caught:' + str(e)

g = guarded()
print('g first', next(g))
print('throw', g.throw(ValueError('x')))
g.close()
print('closed', True)
```

<OutputBox title='对照写法：先自己猜，再点开' output='first sub-ready\ndelegated result:42\ndelegator done None\ng first 1\nthrow caught:x\nclosed True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "def accumulator():\n    total = 0\n    while True:\n        value = yield total\n        if value is None:\n            return total\n        total += value\n\nacc = accumulator()\nprint(&#39;prime&#39;, next(acc))\nprint(&#39;send 10&#39;, acc.send(10))\nprint(&#39;send 5&#39;, acc.send(5))\ntry:\n    acc.send(None)\nexcept StopIteration as e:\n    print(&#39;return value&#39;, e.value)", "note": "生成器双向通信：send / throw / close 与状态机"}, {"label": "对照 / 进阶", "code": "def sub():\n    v = yield &#39;sub-ready&#39;\n    return v * 2\n\ndef delegator():\n    result = yield from sub()\n    yield &#39;result:&#39; + str(result)\n\nd = delegator()\nprint(&#39;first&#39;, next(d))\nprint(&#39;delegated&#39;, d.send(21))\ntry:\n    d.send(None)\nexcept StopIteration as e:\n    print(&#39;delegator done&#39;, e.value)\n\ndef guarded():\n    try:\n        yield 1\n    except ValueError as e:\n        yield &#39;caught:&#39; + str(e)\n\ng = guarded()\nprint(&#39;g first&#39;, next(g))\nprint(&#39;throw&#39;, g.throw(ValueError(&#39;x&#39;)))\ng.close()\nprint(&#39;closed&#39;, True)", "note": "yield from 委托与 StopIteration.value"}]' title='两种写法切换看' />


## CO_GENERATOR 与 gi_frame 里的暂停点

生成器函数在编译期带 `CO_GENERATOR` 标志，调用时 CPython 不执行帧，而是返回一个 `PyGenObject`，帧保存在 `gi_frame` 里、指令指针停在 `YIELD_VALUE` 之后。

3.12 起（3.13 沿用）的字节码以 `RETURN_GENERATOR` 起手，遇到 `YIELD_VALUE` 把值交还调用者并冻结栈帧，`send(v)` 把 v 压回栈、从 `RESUME` 继续。

`yield from` 由 `SEND` / `YIELD_VALUE` 指令对实现委托：调用方 send 的值被转发进子生成器，子生成器 return 时抛 `StopIteration(value)`，外层把它转成 `yield from` 表达式的结果，这正是 `await` 的机器级原型。

PEP 479 在生成器边界检查异常：若 StopIteration 漏出，就包装成 RuntimeError 并保留原异常为 `__cause__`，防止它被 for 循环误判为正常结束。

asyncio 的 `Task.__step` 用 `coro.send(None)` 驱动原生协程，`Future.__await__` 在未完成时 `yield self` 并让出，事件循环在 fd 就绪后把结果 set 回 Future 再 send 进去——`Task` 负责调度、`Future` 负责占位，二者仍是「生成器帧 + 暂停点 + 外部驱动」这套模型。

```python
import dis
import inspect

def gen():
    x = yield 1
    return x

g = gen()
print('state created', inspect.getgeneratorstate(g))
print('first', next(g))
print('state suspended', inspect.getgeneratorstate(g))
print('opnames', [i.opname for i in dis.get_instructions(gen)])
print('CO_GENERATOR', bool(gen.__code__.co_flags & inspect.CO_GENERATOR))
try:
    next(g)
except StopIteration as e:
    print('return value', e.value)
    print('state closed', inspect.getgeneratorstate(g))

def bad():
    yield 1
    raise StopIteration('pep479')

b = bad()
next(b)
try:
    next(b)
except RuntimeError as e:
    print('pep479', 'generator raised StopIteration' in str(e))
```

<OutputBox title='原理验证' output='state created GEN_CREATED\nfirst 1\nstate suspended GEN_SUSPENDED\nopnames [&#39;RETURN_GENERATOR&#39;, &#39;POP_TOP&#39;, &#39;RESUME&#39;, &#39;LOAD_CONST&#39;, &#39;YIELD_VALUE&#39;, &#39;RESUME&#39;, &#39;STORE_FAST&#39;, &#39;LOAD_FAST&#39;, &#39;RETURN_VALUE&#39;, &#39;CALL_INTRINSIC_1&#39;, &#39;RERAISE&#39;]\nCO_GENERATOR True\nreturn value None\nstate closed GEN_CLOSED\npep479 True' />


### 指令指针为什么停在 YIELD_VALUE 之后

<Term word='生成器双向通信' text='包含 `yield` 的函数是生成器函数，调用它只返回生成器对象、一行都不执行。首次必须用 `next(gen)` 或 `gen.send(None)` 启动到第一个 `yield`，否则直接 `gen.send(5)` 会抛 TypeError，提示 can&#39;t send non-None value to a ju…' />

<Term word='yield from 委托' text='`yield from expr`（PEP 380，3.3 起）不只是「逐个产出子迭代器的值」：它建立一条透明通道，调用方 `send` 的值、`throw` 的异常、`close` 的关闭信号都转发给子生成器（只要子生成器有对应方法），子生成器 `return value` 时，整个 `yield from` 表达式…' />


## yield from 的委托语义与 StopIteration.value

`yield from expr`（PEP 380，3.3 起）不只是「逐个产出子迭代器的值」：它建立一条透明通道，调用方 `send` 的值、`throw` 的异常、`close` 的关闭信号都转发给子生成器（只要子生成器有对应方法），子生成器 `return value` 时，整个 `yield from` 表达式的值就是这个 value。

也就是说，`r = yield from inner()` 里的 r 来自 inner 的 return，而不是某个被 yield 出来的元素。

这个语义正是 `await` 的原型：await 一个 future，等价于把当前协程挂起、把结果沿 `yield from` 链路回传。

有两个容易混的点要分清：生成器里 `return` 只是结束并携带值，不会产出给 for 循环；取值要么接住 `yield from` 的结果，要么手动驱动时在 3.7 之后用 `try`/`except` 读 `StopIteration.value`，不能自己 `raise` 出来。

`types.coroutine`（3.5 起）给生成器打上 `CO_ITERABLE_COROUTINE` 标记，使它成为 awaitable，是从生成器协程过渡到原生协程的桥。

**yield / yield from / await 语义对照**

| 形式 | 产出值 | 接收值 | 结果来源 |
| --- | --- | --- | --- |
| yield expr | expr 给调用方 | send 的值成为 yield 表达式结果 | 暂停点本身 |
| yield from sub() | 透明转发 sub 的产出 | 透明转发 send/throw/close | 子生成器 return 的 value |
| await future | 不直接产出，交给事件循环 | 由 Task.send(None) 驱动 | Future 完成后回传结果 |


## 从生成器调度器到 PEP 492 的原生协程

用生成器写协程调度器的最小骨架是：一个 `deque` 就绪队列，每个生成器在 IO 等待处 yield 出一个「等待令牌」，调度器用 `next`/`send` 推进它，就绪后再放回队尾。这正是无栈（stackless）协程：暂停点显式、状态存在生成器帧里、单 OS 线程协作式调度，不需要保存调用栈。

asyncio 里 `Task` 是「被事件循环驱动的协程」，`Future` 是「结果的占位符」，`await` 把二者串起来。

历史包袱在于 asyncio 早期（3.4）用 `@asyncio.coroutine` 装饰生成器当协程，3.5 的 PEP 492 引入 async def / await 与带 `CO_COROUTINE` 标记的原生协程，到 3.11 才移除 `asyncio.coroutine`。

三条 PEP 串起来看：PEP 342（2.5 起，send/throw/close）→ PEP 380（3.3，yield from 委托）→ PEP 492（3.5，async/await）。

读 asyncio 源码时，`Task.__step` 用 `send(None)` 驱动、`Future.__await__` 里 `yield self` 并把结果回传，本质仍是这套生成器协议。

**PEP 演进线与版本**

| PEP / 版本 | 引入能力 | 对应 async 概念 |
| --- | --- | --- |
| PEP 342 / 2.5 | send / throw / close，生成器双向通信 | 协程可接收结果 |
| PEP 380 / 3.3 | yield from 委托、return value、StopIteration.value | await 的原型 |
| PEP 479 / 3.7 默认 | 漏出的 StopIteration 转 RuntimeError | 避免协程错误被 for 吞掉 |
| PEP 492 / 3.5 | async def / await、CO_COROUTINE 原生协程 | Task 与 Future 的分工 |
| 3.11 | 移除 asyncio.coroutine | 生成器协程退出历史主线 |

<FlowTimeline :steps='[{"title": "生成器双向通信：send / throw / c…", "desc": "包含 `yield` 的函数是生成器函数，调用它只返回生成器对象、一行都不执行。首次…", "tone": "blue"}, {"title": "yield from 委托与 StopItera…", "desc": "`yield from expr`（PEP 380，3.3 起）不只是「逐个产出子迭…", "tone": "purple"}, {"title": "从生成器调度器到 PEP 492 的原生协程", "desc": "用生成器写协程调度器的最小骨架是：一个 `deque` 就绪队列，每个生成器在 IO…", "tone": "orange"}, {"title": "工程落地", "desc": "用生成器写一个协作式轮转调度器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 栈-less 协程与回调写法的调用栈

<ConceptDiagram type='layers3' title='第 067 讲 · 分层视角' labels='生成器双向通信：send / throw…|yield from 委托与 StopI…|从生成器调度器到 PEP 492 的原生…|PEP 380 / 492' caption='从生成器调度器到 PEP 492 的原生协程' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 PEP 380 / 492 落在哪一层。


## 用生成器写一个协作式轮转调度器

要理解 asyncio 的事件循环，先手写一个最小调度器：每个任务是一个生成器，在需要「等待」的地方 yield 出一个令牌，调度器用 `deque` 维护就绪队列，每次 `next` 推进一个任务，令牌为 `'wait'` 就重新入队、任务结束（StopIteration）就出队。

这就是无栈协程的原型——暂停点显式、状态在帧里、单线程协作式推进，不需要回调嵌套。下面片段让三个任务各跑几步，打印轮转顺序与总步数。把 `'wait'` 换成真实 fd 就绪判断、把 `send(None)` 换成送回 IO 结果，就得到 asyncio 里 Task/Future 分工的雏形。

```python
from collections import deque

def task(name, steps):
    for i in range(steps):
        yield ('ready', name, i)
        if i + 1 < steps:
            yield ('wait', name, i)

def run(tasks):
    queue = deque(tasks)
    log = []
    while queue:
        t = queue.popleft()
        try:
            token = next(t)
            log.append(token)
            if token[0] == 'wait':
                try:
                    next(t)
                    queue.append(t)
                except StopIteration:
                    pass
            else:
                queue.append(t)
        except StopIteration:
            pass
    return log

if __name__ == '__main__':
    out = run([task('A', 3), task('B', 2)])
    print('steps', len(out))
    print('first', out[0])
    print('round robin', [x[1] for x in out if x[0] == 'ready'])
```

<Callout type="idea" title='落地提示' text='理解这条演进线，才能读懂 asyncio 里 Future / Task 的分工与历史包袱' />

<CheckList id='P067a' title='上线前自检' :items='["能复现并解释「第一次就 gen.send(5) 驱动生成器」", "能复现并解释「在生成器里 raise StopIteration 想结束循…」", "能复现并解释「把 yield from 当成普通遍历，无视委托语义」", "能用一条命令验证 生成器双向通信", "关键路径有自动化测试与失败分支"]' />

<Callout type="warn" title='本讲最容易踩的坑' text='第一次就 gen.send(5) 驱动生成器：生成器尚未启动到第一个 yield，没有表达式可接收值' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：第一次就 gen.send(5) 驱动生成器", "body": "生成器尚未启动到第一个 yield，没有表达式可接收值", "tip": "先 next(gen) 或 gen.send(None)  priming，再 send 非 None 值"}, {"title": "第 2 步：在生成器里 raise StopIterat…", "body": "PEP 479（3.7+ 默认）把漏出的 StopIteration 转成 RuntimeError: generator raised StopIteration", "tip": "用 return value 正常结束；手动驱动时在 try/except StopIteration 里读 e.value"}, {"title": "第 3 步：把 yield from 当成普通遍历，无视…", "body": "它还会转发 send/throw/close，并以子生成器 return 值作为表达式结果", "tip": "需要接收结果时写 r = yield from sub()；只遍历用 for x in sub() 即可"}]' />


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 第一次就 gen.send(5) 驱动生成器 | 生成器尚未启动到第一个 yield，没有表达式可接收值 | 先 next(gen) 或 gen.send(None)  priming，再 send 非 None 值 |
| 在生成器里 raise StopIteration 想结束循环 | PEP 479（3.7+ 默认）把漏出的 StopIteration 转成 RuntimeError: generator raised StopIteration | 用 return value 正常结束；手动驱动时在 try/except StopIteration 里读 e.value |
| 把 yield from 当成普通遍历，无视委托语义 | 它还会转发 send/throw/close，并以子生成器 return 值作为表达式结果 | 需要接收结果时写 r = yield from sub()；只遍历用 for x in sub() 即可 |


## genobject.c 的 gen_send_ex2 与 SEND 指令

正文把 `yield from` 讲成透明委托，落到 3.13 字节码是另一幅图：dis 显示 `RETURN_GENERATOR`、`GET_YIELD_FROM_ITER`、`SEND`、`YIELD_VALUE`、`END_SEND`。

`GET_YIELD_FROM_ITER` 把表达式归一成迭代器；`SEND` 是委托核心，栈顶是要发给子生成器的值、下面是委托对象，委托对象有 send 方法就调用 `send(v)`，否则要求 v 为 None 并退化为 `next(it)`。

执行侧在 CPython 源码 `Objects/genobject.c` 的 `gen_send_ex2` 里：恢复 `gi_frame` 的 `_PyInterpreterFrame`，把 arg 压回栈作为上一个 `yield` 表达式的值，exc 为真时改为注入异常，再跑到下一个 `YIELD_VALUE`。

`gen.throw` 以 `exc=1` 进同一路径，`gen.close` 注入 `GeneratorExit`。由此划出边界：暂停点固定在字节码里，帧状态保存在堆上的 `PyGenObject` 而非 C 调用栈，协程不必保存栈、可在任意深度恢复，代价是暂停点必须显式写出。

```python
import dis
import inspect
import types

def inner():
    yield 1
    return 9

def outer():
    r = yield from inner()
    return r

ops = [i.opname for i in dis.get_instructions(outer)]
print('send opcode', 'SEND' in ops)
print('yield opcode', 'YIELD_VALUE' in ops)
print('generator flag', bool(outer.__code__.co_flags & inspect.CO_GENERATOR))

@types.coroutine
def legacy():
    yield
print('iterable coroutine flag', bool(legacy.__code__.co_flags & inspect.CO_ITERABLE_COROUTINE))

```

<OutputBox title='扩展示例运行结果' output='send opcode True\nyield opcode True\ngenerator flag True\niterable coroutine flag True' />

<LineByLine code='import dis\nimport inspect\nimport types\n\ndef inner():\n    yield 1\n    return 9\n\ndef outer():\n    r = yield from inner()\n    return r\n\nops = [i.opname for i in dis.get_instructions(outer)]\nprint(&#39;send opcode&#39;, &#39;SEND&#39; in ops)\nprint(&#39;yield opcode&#39;, &#39;YIELD_VALUE&#39; in ops)\nprint(&#39;generator flag&#39;, bool(outer.__code__.co_flags &amp; inspect.CO_GENERATOR))\n\n@types.coroutine\ndef legacy():\n    yield\nprint(&#39;iterable coroutine flag&#39;, bool(legacy.__code__.co_flags &amp; inspect.CO_ITERABLE_COROUTINE))\n' :notes='["dis 读出函数编译后的指令名列表", "3.11 起 yield from 编译出 SEND 指令", "types.coroutine 给生成器打上 0x100 让 Awaitable 放行", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def inner():` 的作用，可对照上方输出逐项核对。", "这一行 `yield 1` 的作用，可对照上方输出逐项核对。", "这一行 `return 9` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def outer():` 的作用，可对照上方输出逐项核对。", "这一行 `r = yield from inner()` 的作用，可对照上方输出逐项核对。", "这一行 `return r` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `ops = [i.opname for i in dis.get_instructions(outer)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;send opcode&#39;, &#39;SEND&#39; in ops)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;yield opcode&#39;, &#39;YIELD_VALUE&#39; in ops)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;generator flag&#39;, bool(outer.__code__.co_flags` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `@types.coroutine` 的作用，可对照上方输出逐项核对。", "这一行 `def legacy():` 的作用，可对照上方输出逐项核对。", "这一行 `yield` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;iterable coroutine flag&#39;, bool(legacy.__code_` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### PyGenObject 的 gi_yieldfrom 与 frame 状态

<ConceptDiagram type='flow4' title='第 067 讲 · 扩展图解' labels='SEND 取栈顶 send 值|gi_yieldfrom 委托链|YIELD_VALUE 回传|gen_send_ex2 恢复帧' caption='SEND 循环转发调用方的值给子生成器并回传产出，直到 StopIteration.value 落入结果。' />


## co_flags 四类协程标志与 types.coroutine 的桥

头文件 `Include/cpython/code.h` 用 co_flags 的位区分四类可暂停函数：`CO_GENERATOR(0x20)` 给含 yield 的，`CO_COROUTINE(0x80)` 给 async def，`CO_ASYNC_GENERATOR(0x200)` 给 async def 里还带 yield 的，`CO_ITERABLE_COROUTINE(0x100)` 是 PEP 492 之前的桥。

`types.coroutine` 给生成器打上 0x100，使 `collections.abc.Awaitable` 检查通过，于是 3.4 的 `asyncio.coroutine` 生成器能被原生 await 消费。

桥解释了 asyncio 的历史包袱：`Future.__await__` 里写 `yield self` 再 `return self.result()`，仍是生成器协议；`Task.__step` 用 `send(None)` 驱动，`__wakeup` 把结果送回。

编译器还靠这些位立规矩：`CO_COROUTINE` 的函数里出现 yield 或 yield from 直接报语法错，保证原生协程的暂停点只有 await。PEP 342 到 380 再到 492，是把「可暂停」逐步收敛成有独立标志位的对象类别。

**co_flags 四类可暂停标志**

| 标志 | 十六进制 | 产生方式 | 能否被 await |
| --- | --- | --- | --- |
| CO_GENERATOR | 0x20 | 含 yield 的函数 | 否，除非另加 CO_ITERABLE_COROUTINE |
| CO_ITERABLE_COROUTINE | 0x100 | types.coroutine 装饰生成器 | 是 |
| CO_COROUTINE | 0x80 | async def | 是 |
| CO_ASYNC_GENERATOR | 0x200 | async def 且含 yield | 否，用 async for |

<Term word='gi_yieldfrom' text='PyGenObject 里指向当前 yield from 委托对象的字段；SEND 通过它把 send 与 throw 转发给子生成器，调试器也顺着这条链重建委托栈。' />


### PEP 380 六段式等价展开的 throw/close 分发

PEP 380 给了 `RESULT = yield from EXPR` 的六段式展开：取 `iter(EXPR)`，循环里 next、send、throw 分头处理，子迭代器抛 StopIteration 时取 `_e.value` 作结果，并把外层 throw 与 close 转发进去。

这解释了两点：`r = yield from inner()` 拿到的是 inner 的 return 而非产出值，`send(None)` 能穿到最里层。

PEP 479 的动机也在此：StopIteration 漏出会被 for 循环吞掉，3.7 起转成 RuntimeError。

下面用 `delegate` 复现委托与返回值，观察 `raise StopIteration` 被转换后的类型。

```python
def inner():
    yield 1
    yield 2
    return 'done'

def delegate(it):
    try:
        y = next(it)
    except StopIteration as e: return e.value
    while True:
        sent = yield y
        try:
            y = it.send(sent)
        except StopIteration as e: return e.value

g = delegate(inner())
print('first', next(g))
print('second', g.send(None))
try:
    g.send(None)
except StopIteration as e:
    print('return value', e.value)

def broken():
    yield 1
    raise StopIteration('leaked')

b = broken()
print('yield', next(b))
try:
    next(b)
except RuntimeError as e:
    print('converted', type(e).__name__)

```


## PEP 479 把漏出的 StopIteration 转成 RuntimeError 的复盘

<Quiz no='067-1' q='在 3.13 中，一个生成器函数体内显式 raise StopIteration(&#39;leaked&#39;) 并被下一步驱动，最终外部观察到的是什么？' :options='["StopIteration(&#39;leaked&#39;) 原样抛出，value 为 leaked", "GeneratorExit，等价于 close() 的注入", "RuntimeError: generator raised StopIteration，原异常挂在 __cause__ 上", "无任何异常，生成器静默结束并返回 leaked"]' answer="2" explain='PEP 479 自 3.7 起生效：StopIteration 从生成器帧漏出时，解释器在边界把它转成 RuntimeError 并把原异常挂在 __cause__ 上，避免 for 循环误判为正常终止。A 是未开 generator_stop 的旧行为，B 混淆了 close() 的 GeneratorExit，D 是被静默吞掉的 bug。' />

<Exercise title='用 co_flags 区分三类可暂停函数' task='定义生成器、types.coroutine 装饰的生成器、async def 原生协程，逐个打印 CO_GENERATOR / CO_ITERABLE_COROUTINE / CO_COROUTINE 三个位，说明哪一类是过渡期的桥。' solution='import inspect\nimport types\n\ndef gen():\n    yield 1\n\n@types.coroutine\ndef bridge():\n    yield\n\nasync def native():\n    pass\n\nfor name, fn in [(&#39;gen&#39;, gen), (&#39;bridge&#39;, bridge), (&#39;native&#39;, native)]:\n    f = fn.__code__.co_flags\n    print(name, bool(f &amp; inspect.CO_GENERATOR), bool(f &amp; inspect.CO_ITERABLE_COROUTINE), bool(f &amp; inspect.CO_COROUTINE))\n' explain='输出为 gen True/False/False、bridge True/True/False、native False/False/True。bridge 同时带 CO_GENERATOR 与 CO_ITERABLE_COROUTINE，仍是生成器、只多了 0x100 让 Awaitable 放行，是 3.4 到 3.5 的桥；原生协程只有 CO_COROUTINE，禁止函数体里出现 yield。' />


## 练习、自测与速记

<Exercise title='基础：用 send 写一个累加协程' task='写生成器累加器，next 启动后 send(10)、send(5)，再 send(None) 结束并从 StopIteration.value 取回 15；说明首帧为何不能 send 非 None。' solution='def acc():\n    total = 0\n    while True:\n        v = yield total\n        if v is None:\n            return total\n        total += v\ng = acc()\nprint(next(g), g.send(10), g.send(5))\ntry:\n    g.send(None)\nexcept StopIteration as e:\n    print(&#39;value&#39;, e.value)' explain='调用生成器函数只建对象、帧未启动，第一个 yield 之前没有表达式可接收值，故必须 next 或 send(None) 启动；return 值挂在 StopIteration.value 上。' />

<Exercise title='进阶：用 yield from 取回子生成器的 return 值' task='子生成器接收一个值并 return 其两倍；外层用 r = yield from sub() 接住结果再 yield 出去；驱动外层并打印两处结果。' solution='def sub():\n    v = yield &#39;need&#39;\n    return v * 2\ndef outer():\n    r = yield from sub()\n    yield &#39;got:&#39; + str(r)\no = outer()\nprint(next(o))\nprint(o.send(21))\ntry:\n    o.send(None)\nexcept StopIteration as e:\n    print(&#39;outer return&#39;, e.value)' explain='yield from 把 send 透明转发给 sub，sub 的 return 42 成为表达式结果赋给 r，外层再 yield &#39;got:42&#39;；这正是 await 回传结果的原型。' />

<Quiz no='067-2' q='yield from sub() 表达式的值来自哪里？' :options='["子生成器 return 的 value（经 StopIteration.value 回传）", "sub 最后一个 yield 出来的元素", "永远是 None", "调用方最后一次 send 的值"]' answer="0" explain='PEP 380 规定子生成器 return value 时，yield from 表达式求值得到该 value；send/throw/close 也透明转发。这是 await 回传结果的原型。' />

<Quiz no='067-3' q='生成器里直接 raise StopIteration(&#39;done&#39;)，3.7+ 会怎样？' :options='["被 PEP 479 转成 RuntimeError: generator raised StopIteration", "正常结束且 value 为 done", "被 for 循环静默吞掉", "抛 TypeError"]' answer="0" explain='PEP 479 自 3.7 默认生效，防止漏出的 StopIteration 被 for/驱动逻辑误判为正常终止；正确写法是 return value，手动驱动时从 e.value 读。' />

<Quiz no='067-4' q='关于 async/await 与生成器协程的演进，正确的是？' :options='["PEP 342 加 send/throw/close，PEP 380 加 yield from，PEP 492 引入原生协程", "async/await 与生成器毫无关系", "await 是 Python 2 就有的语法", "Task 负责占位、Future 负责调度"]' answer="0" explain='演进线是 PEP 342 → 380 → 492；asyncio 里 Task 负责调度、Future 负责结果占位，Task.__step 仍用 send(None) 驱动协程。' />

<Predict no='067-5' q='生成器刚创建（GEN_CREATED）就执行 gen.send(5)，会发生什么？' :options='["抛 TypeError: can&#39;t send non-None value to a just-started generator", "返回第一个 yield 的值 5", "正常启动并丢弃 5", "抛 StopIteration"]' answer='0' output='TypeError: can&#39;t send non-None value to a just-started generator' explain='生成器帧尚未运行到任何 yield，没有表达式可接收传入值；必须先用 next(gen) 或 send(None) priming 到第一个暂停点。' />

<FillBlank no='067-6' tpl='___ accumulator():' :answers='["def"]' hint='回想本讲关于 生成器双向通信 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 生成器双向通信：send / throw / close 与状态机 的落点。' />

<KnowledgeCard :points='["生成器函数调用只返回对象；首次用 next(gen) 或 gen.send(None) 启动，send(v) 把 v 作为当前 yield 表达式的值", "yield from 透明转发 send/throw/close，并以子生成器 return 的 value 作为表达式结果（PEP 380）", "生成器 return value 挂在 StopIteration.value；PEP 479（3.7 起默认）把漏出的 StopIteration 转成 RuntimeError", "gen.throw 在暂停点抛异常可被接住；gen.close 抛 GeneratorExit，此时再 yield 会报 generator ignored GeneratorExit", "inspect.getgeneratorstate 四态 GEN_CREATED/RUNNING/SUSPENDED/CLOSED；CO_GENERATOR 为 32", "演进线 PEP 342 → 380 → 492；asyncio 里 Task 调度、Future 占位，Task.__step 用 send(None) 驱动"]' :pitfalls='["第一次就 gen.send(5) 驱动生成器", "在生成器里 raise StopIteration 想结束循环", "把 yield from 当成普通遍历，无视委托语义", "在生成器里混用 return value 与 yield，容易搞不清 StopIteration.value 到底从哪来"]' summary='async/await 不是凭空出现的语法：把生成器的暂停点用于 IO 等待，再配一个调度器，就是协程的原型' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 生成器函数调用只返回对象；首次用 next(gen) 或 gen.send(None) 启动，send(v) 把 v 作为当前 yield 表达式的值 | 建立直觉 |
| yield from 透明转发 send/throw/close，并以子生成器 return 的 value 作为表达式结果（PEP 380） | 跑通示例 |
| 生成器 return value 挂在 StopIteration.value；PEP 479（3.7 起默认）把漏出的 StopIteration 转成 RuntimeError | 深入边界 |
| gen.throw 在暂停点抛异常可被接住；gen.close 抛 GeneratorExit，此时再 yield 会报 generator ignored GeneratorExit | 工程落地 |
| inspect.getgeneratorstate 四态 GEN_CREATED/RUNNING/SUSPENDED/CLOSED；CO_GENERATOR 为 32 | 随堂检测 |
| 演进线 PEP 342 → 380 → 492；asyncio 里 Task 调度、Future 占位，Task.__step 用 send(None) 驱动 | 复盘 |

1. 生成器函数调用只返回对象；首次用 next(gen) 或 gen.send(None) 启动，send(v) 把 v 作为当前 yield 表达式的值

2. yield from 透明转发 send/throw/close，并以子生成器 return 的 value 作为表达式结果（PEP 380）

3. 生成器 return value 挂在 StopIteration.value；PEP 479（3.7 起默认）把漏出的 StopIteration 转成 RuntimeError

[下一讲：async / await 与协程对象](/concurrency/async-await)

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 生成器双向通信 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/067-generator-coroutine.py`

```bash
python3 examples/lessons/067-generator-coroutine.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/067-generator-coroutine.py) · [全部示例代码索引](/examples/)
