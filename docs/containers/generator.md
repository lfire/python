---
title: 第 026 讲 · 生成器与 yield：send / throw / close
description: 掌握协程的雏形与状态机写法
---

<StageHeader stage='L2 · 容器与序列' level='★★★☆☆' time='35 分钟' goal='掌握协程的雏形与状态机写法' prereq='第 025 讲 · 迭代协议：iterable、iterator 与惰性求值' />

# 第 026 讲 · 生成器与 yield：send / throw / close

要是能把函数停在某处、下次从那儿接着跑，不少活儿会轻很多。这一讲看生成器与手写迭代器的不同：一个 yield，函数就成了可暂停的状态机。

一个报表函数逐行吐数据、中途打开文件，调用方提前收手时句柄一直没还，描述符不够用；也有人刚建好生成器就想往里送值被挡回，还有人把清理写错地方，收尾始终没执行。我们先看生成器函数里 yield 怎样把局部变量与指令指针留在帧里、双向通信怎么接上；再讲委托、抛入与关闭何时触发收尾；最后说清它作为协程雏形的位置。需要你熟悉迭代协议、函数与 finally。学完你能写出内存恒定的管道，也知道提前收手时由谁把摊子收干净。


## 刚创建的生成器，一 send 就抛 TypeError

一个报表生成器用 yield 逐行吐出数据，函数里打开了一个文件句柄却只在正常跑完时关闭；调用方中途 break 提前退出，生成器被挂起，句柄一直不释放，跑几百次后进程把文件描述符用光。

更隐蔽的是有人用 `g.send(5)` 启动一个刚创建的生成器，直接抛 TypeError: can't send non-None value to a just-started generator；

还有人以为 `close()` 只是停止迭代，不知道它会在暂停处抛 GeneratorExit 来触发 finally，于是在 except Exception 里写清理逻辑却永远不执行。这些现象都指向同一件事：yield 把函数变成了可暂停的状态机，帧里保存着局部变量与指令指针。

本讲把 send 双向通信、yield from 委托、throw / close 与清理、以及生成器作为协程基座的机制讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='生成器持有文件句柄迟迟不释放：调用方提前 break 后生成器被挂起，没有 close() 就不会执行 finally' />


## 可暂停的状态机：帧、启动与 send 双向通信

含 yield 的函数是生成器函数，调用它并不执行函数体，而是返回一个 generator 对象：此时 code object 的 co_flags 含 CO_GENERATOR，gi_frame 已经存在但指令指针停在最开头，`inspect.getgeneratorstate` 返回 GEN_CREATED。

第一次必须用 `next(g)` 或 `g.send(None)` 启动，执行到第一个 yield 暂停，yield 表达式的值成为这次产出的结果；此后每次 next / send 都从上次暂停处继续执行局部变量，直到下一个 yield。

yield 是表达式，可以写 `value = yield` total：`g.send(10)` 恢复执行，并把 10 作为当前 yield 表达式的返回值赋给 value，于是调用方与生成器形成双向通信。

刚创建时不能 send 非 None 值，否则抛 TypeError: can't send non-None value to a just-started generator，因为还没有 yield 表达式在等待接收。

生成器里的 return value 不是把值给调用方，而是让它成为 `StopIteration.value`（PEP 380，3.3+），调用方在 except StopIteration as e 里用 `e.value` 取到；

这也是 yield from 能把子生成器 return 值带回来的原因。

```python
import inspect

def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            break
        total += value
    return total

g = accumulator()
print('state created', inspect.getgeneratorstate(g))
print('prime', next(g))
print('send 10', g.send(10), 'send 5', g.send(5))
try:
    g.send(None)
except StopIteration as e:
    print('return value', e.value)
print('state closed', inspect.getgeneratorstate(g))

def source(n):
    for i in range(n):
        yield i
    return 'source done'

def wrapper():
    result = yield from source(3)
    yield 'got: ' + result

print('yield from', list(wrapper()))

def with_cleanup(log):
    try:
        yield 'working'
        yield 'more'
    finally:
        log.append('cleaned')

log = []
c = with_cleanup(log)
print('first', next(c))
print('throw', end=' ')
try:
    c.throw(ValueError('stop'))
except ValueError as e:
    print(type(e).__name__, log)
c.close()
print('after close', log, inspect.getgeneratorstate(c))
```

<OutputBox title='主示例运行结果' output='state created GEN_CREATED\nprime 0\nsend 10 10 send 5 15\nreturn value 15\nstate closed GEN_CLOSED\nyield from [0, 1, 2, &#39;got: source done&#39;]\nfirst working\nthrow ValueError [&#39;cleaned&#39;]\nafter close [&#39;cleaned&#39;] GEN_CLOSED' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import inspect\n\ndef accumulator():\n    total = 0\n    while True:\n        value = yield total\n        if value is None:\n            break\n        total += value\n    return total\n\ng = accumulator()\nprint(&#39;state created&#39;, inspect.getgeneratorstate(g))\nprint(&#39;prime&#39;, next(g))\nprint(&#39;send 10&#39;, g.send(10), &#39;send 5&#39;, g.send(5))\ntry:\n    g.send(None)\nexcept StopIteration as e:\n    print(&#39;return value&#39;, e.value)\nprint(&#39;state closed&#39;, inspect.getgeneratorstate(g))\n\ndef source(n):\n    for i in range(n):\n        yield i\n    return &#39;source done&#39;\n\ndef wrapper():\n    result = yield from source(3)\n    yield &#39;got: &#39; + result\n\nprint(&#39;yield from&#39;, list(wrapper()))\n\ndef with_cleanup(log):\n    try:\n        yield &#39;working&#39;\n        yield &#39;more&#39;\n    finally:\n        log.append(&#39;cleaned&#39;)\n\nlog = []\nc = with_cleanup(log)\nprint(&#39;first&#39;, next(c))\nprint(&#39;throw&#39;, end=&#39; &#39;)\ntry:\n    c.throw(ValueError(&#39;stop&#39;))\nexcept ValueError as e:\n    print(type(e).__name__, log)\nc.close()\nprint(&#39;after close&#39;, log, inspect.getgeneratorstate(c))' :notes='["导入 inspect 读取生成器状态", "定义一个累加器生成器，演示双向通信", "累加值保存在局部变量里，跨 yield 保留", "循环等待调用方 send 值", "yield 是表达式，send 的值会成为 value", "收到 None 就结束循环", "跳出循环", "把新值累加进 total", "return 的值会成为 StopIteration.value", "调用生成器函数并不执行函数体，只返回 generator", "刚创建时状态是 GEN_CREATED", "next 启动并产出初始 total 0", "send 10 让 value 等于 10、total 变 10 并产出 10", "send None 触发 break，生成器执行 return 后抛 StopIteration", "捕获 StopIteration 并取出 return 值 15", "从异常的 value 属性读到生成器的返回值", "结束后状态变为 GEN_CLOSED", "子生成器产出若干值并 return 一个标记", "循环产出 0 到 n-1", "return 值会被 yield from 接收", "外层生成器用 yield from 委托给子生成器", "子生成器的 return 值成为 yield from 表达式的结果", "再产出一个拼接后的字符串", "list 消费委托链，拿到四个值", "带 finally 清理的生成器", "try 包住 yield，保证异常路径也走 finally", "第一个暂停点", "第二个暂停点", "finally 是唯一可靠的清理位置", "把清理事件写进外部列表便于观测", "构造日志列表", "创建生成器并启动到第一个 yield", "打印第一个产出", "打印 throw 前缀，稍后拼上异常信息", "在暂停处抛 ValueError", "生成器内没有 except，异常向外传播", "finally 已执行，日志里出现 cleaned", "对已结束的生成器 close 是幂等的", "日志只记录一次，状态为 GEN_CLOSED", "close() 抛 GeneratorExit（继承 BaseException）触发 finally；清理只能写进 finally，except Exception 拦不住", "3.7 起 PEP 479 把生成器内 StopIteration 转成 RuntimeError；用 return 结束而非手动 raise", "生成器是 async/await 的基座；持有资源时用 try/finally 并让调用方提前退出时显式 close()"]' title='第 026 讲 · 生成器与 yield：send / throw / close' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='含 yield 的函数是生成器函数，调用它并不执行函数体，而是返回一个 generator 对象：此时 code object 的 co_flags 含 CO_GENERATOR，gi_frame 已经存在但指令指针停在最开头，inspect.getgeneratorstate 返回 GEN_CRE' />


## 生成器帧里留住了什么：局部变量与指令指针

含 yield 的函数调用后并不执行函数体，只返回一个 generator：code object 的 co_flags 含 CO_GENERATOR，gi_frame 已经分配但 f_lasti 停在开头，`inspect.getgeneratorstate` 为 GEN_CREATED。

ceval 执行到 YIELD_VALUE 时把值交给调用方、把当前帧的指令指针与局部变量原样留在 gi_frame 里，下一次 next / send 从该位置继续，这就是可暂停状态机的全部实现。`send(value)` 把 value 压回栈作为 yield 表达式的返回值；

刚创建时没有等待接收的 yield，send 非 None 会抛 TypeError。`close()` 在暂停处注入 GeneratorExit（继承 BaseException，故 except Exception 拦不住），沿帧展开执行 finally 后把状态置为 GEN_CLOSED；

若 finally 里再 yield 会抛 RuntimeError: generator ignored GeneratorExit。

生成器 return value 被写成 `StopIteration.value`（PEP 380），yield from 据此把子生成器结果回传并把 send / throw / close 沿委托链转发。

PEP 492 的 async/await 正是复用这套帧暂停与恢复机制，只是换成原生协程对象。

<ConceptDiagram type='flow4' title='第 026 讲 · 可暂停的状态机：帧、启动与 send 双向通信' labels='可暂停的状态机：帧、启动与 send 双向通|yield from 委托、throw / |生成器作为协程基座与工程边界' caption='掌握协程的雏形与状态机写法' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 生成器对象的方法与状态

**生成器对象的方法与状态**

| 方法 / 状态 | 行为 | 约束 |
| --- | --- | --- |
| next(g) / g.send(None) | 启动或恢复，产出下一个 yield 的值 | 首次必须用它们启动 |
| g.send(value) | 恢复并把 value 作为当前 yield 表达式的返回值 | 对刚创建的生成器 send 非 None 抛 TypeError |
| g.throw(exc) | 在暂停处抛异常，可被生成器内 except 接住 | 未接住则向外传播，finally 仍执行 |
| g.close() | 在暂停处抛 GeneratorExit 触发 finally | GeneratorExit 继承 BaseException，except Exception 拦不住 |
| return value | 值成为 StopIteration.value（3.3+） | 用 e.value 取，或由 yield from 接收 |
| GEN_CREATED / SUSPENDED / CLOSED | inspect.getgeneratorstate 的四种状态 | 排查生成器卡在哪一步 |

```python
import inspect, dis

def gen():
    x = 1
    yield x
    x += 1
    yield x

g = gen()
print('not started', g.gi_frame is not None, inspect.getgeneratorstate(g))
print('locals before', g.gi_frame.f_locals)
print('first', next(g))
print('locals after', g.gi_frame.f_locals)
print('running flag', g.gi_running)
print('state', inspect.getgeneratorstate(g))
print('CO_GENERATOR flag', bool(gen.__code__.co_flags & inspect.CO_GENERATOR))
print('YIELD in bytecode', 'YIELD' in dis.Bytecode(gen).dis())
```

<OutputBox title='原理验证' output='not started True GEN_CREATED\nlocals before {}\nfirst 1\nlocals after {&#39;x&#39;: 1}\nrunning flag False\nstate GEN_SUSPENDED\nCO_GENERATOR flag True\nYIELD in bytecode True' />


## yield from 委托、throw / close 与清理契约

yield from iterable（PEP 380，3.3+）把产出与接收全部委托给子迭代器：调用方 send 的值会转发到子生成器，子生成器耗尽后的 return 值成为整个 yield from 表达式的结果，throw 与 close 也会沿委托链传下去，省掉手写转发样板。

`g.throw(exc)` 在生成器暂停处抛出指定异常：若生成器内 try/except 接住就能继续产出，否则异常向外传播，但 finally 一定执行。

`g.close()` 更特殊，它在暂停处抛 GeneratorExit（继承 BaseException 而非 Exception），触发生成器里的 finally 做资源释放；

生成器收到 GeneratorExit 后必须正常退出，若还在 finally 里再 yield 会抛 RuntimeError: generator ignored GeneratorExit。

因为 GeneratorExit 不在 Exception 之下，except Exception 捕获不到它，所以清理逻辑只能写进 finally，不能写进普通 except。`close()` 对已结束的生成器是幂等的，不会重复执行 finally。

`contextlib.contextmanager` 正是用'生成器 + 单次 yield + finally'实现 with 的进出配对，这是生成器协议最直接的工程应用。

```python
from contextlib import contextmanager

def guarded(log):
    try:
        yield 'a'
    except Exception:
        log.append('Exception branch')
    finally:
        log.append('finally branch')

log = []
g = guarded(log)
print('next', next(g))
g.close()
print('close triggers finally', log)
print('GeneratorExit is BaseException', GeneratorExit.__mro__[1].__name__)

@contextmanager
def tag(name):
    log.append('enter ' + name)
    yield name
    log.append('exit ' + name)

with tag('T') as t:
    print('inside', t)
print('contextmanager log', log)
```

<OutputBox title='对照写法：先自己猜，再点开' output='next a\nclose triggers finally [&#39;finally branch&#39;]\nGeneratorExit is BaseException BaseException\ninside T\ncontextmanager log [&#39;finally branch&#39;, &#39;enter T&#39;, &#39;exit T&#39;]' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import inspect\n\ndef accumulator():\n    total = 0\n    while True:\n        value = yield total\n        if value is None:\n            break\n        total += value\n    return total\n\ng = accumulator()\nprint(&#39;state created&#39;, inspect.getgeneratorstate(g))\nprint(&#39;prime&#39;, next(g))\nprint(&#39;send 10&#39;, g.send(10), &#39;send 5&#39;, g.send(5))\ntry:\n    g.send(None)\nexcept StopIteration as e:\n    print(&#39;return value&#39;, e.value)\nprint(&#39;state closed&#39;, inspect.getgeneratorstate(g))\n\ndef source(n):\n    for i in range(n):\n        yield i\n    return &#39;source done&#39;\n\ndef wrapper():\n    result = yield from source(3)\n    yield &#39;got: &#39; + result\n\nprint(&#39;yield from&#39;, list(wrapper()))\n\ndef with_cleanup(log):\n    try:\n        yield &#39;working&#39;\n        yield &#39;more&#39;\n    finally:\n        log.append(&#39;cleaned&#39;)\n\nlog = []\nc = with_cleanup(log)\nprint(&#39;first&#39;, next(c))\nprint(&#39;throw&#39;, end=&#39; &#39;)\ntry:\n    c.throw(ValueError(&#39;stop&#39;))\nexcept ValueError as e:\n    print(type(e).__name__, log)\nc.close()\nprint(&#39;after close&#39;, log, inspect.getgeneratorstate(c))", "note": "可暂停的状态机：帧、启动与 send 双向通信"}, {"label": "对照 / 进阶", "code": "from contextlib import contextmanager\n\ndef guarded(log):\n    try:\n        yield &#39;a&#39;\n    except Exception:\n        log.append(&#39;Exception branch&#39;)\n    finally:\n        log.append(&#39;finally branch&#39;)\n\nlog = []\ng = guarded(log)\nprint(&#39;next&#39;, next(g))\ng.close()\nprint(&#39;close triggers finally&#39;, log)\nprint(&#39;GeneratorExit is BaseException&#39;, GeneratorExit.__mro__[1].__name__)\n\n@contextmanager\ndef tag(name):\n    log.append(&#39;enter &#39; + name)\n    yield name\n    log.append(&#39;exit &#39; + name)\n\nwith tag(&#39;T&#39;) as t:\n    print(&#39;inside&#39;, t)\nprint(&#39;contextmanager log&#39;, log)", "note": "yield from 委托、throw / close 与清理契约"}]' title='两种写法对照' note='差异集中在 生成器函数与 yield；先看输出，再找背后的规则。' />

**yield from 与版本差异**

| 版本 / 特性 | 内容 | 影响 |
| --- | --- | --- |
| 3.3 PEP 380 | yield from 委托子迭代器、转发 send/throw/close、接收 return 值 | 省掉手写转发样板 |
| 3.3 PEP 380 | 生成器 return value 写入 StopIteration.value | 子生成器可向父生成器回传结果 |
| 3.5 PEP 492 | async/await 基于生成器协议实现原生协程 | 生成器是协程雏形 |
| 3.7 PEP 479 | 生成器内 StopIteration 转成 RuntimeError | 结束用 return，不手动 raise |
| 3.6 异步生成器 | async def 里可用 yield | 语义沿袭 send / throw / close |

<FlowTimeline :steps='[{"title": "可暂停的状态机：帧、启动与 send 双向通信", "desc": "含 yield 的函数是生成器函数，调用它并不执行函数体，而是返回一个 genera…", "tone": "blue"}, {"title": "yield from 委托、throw / close 与清理契约", "desc": "yield from iterable（PEP 380，3.3+）把产出与接收全部委…", "tone": "purple"}, {"title": "生成器作为协程基座与工程边界", "desc": "生成器把&#39;执行到一半暂停、保留栈帧、之后再恢复&#39;这件事做成了语言级能力，这正是后来 …", "tone": "orange"}, {"title": "工程落地", "desc": "带清理的可暂停数据管道：send 调阈值、yield from 串联", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 清理与失效信号：close 时 finally 为什么才可靠

**清理与失效信号**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 生成器持有文件句柄不释放 | 调用方提前 break，生成器被挂起且没 close | try/finally 写清理，调用方用 contextlib.closing 或显式 close() |
| except Exception 收不到 close 的清理 | GeneratorExit 继承 BaseException 而非 Exception | 清理逻辑一律放进 finally |
| close 后再 yield 抛 RuntimeError | generator ignored GeneratorExit | 收到 GeneratorExit 后必须正常退出，别在 finally 里 yield |
| g.send(5) 启动刚创建的生成器报错 | 还没有 yield 表达式在等待接收 | 先 next(g) 或 g.send(None) 启动 |

<Callout type="warn" title='本讲最容易踩的坑' text='生成器持有文件句柄迟迟不释放：调用方提前 break 后生成器被挂起，没有 close() 就不会执行 finally' />


## 生成器作为协程基座与工程边界

生成器把'执行到一半暂停、保留栈帧、之后再恢复'这件事做成了语言级能力，这正是后来 async/await 的基座：3.5 的 PEP 492 用 `types.coroutine` 与 await 把生成器协议包装成原生协程，3.6 又加入异步生成器，语义上仍沿袭 send / throw / close 与 yield from 的委托模型。

工程上有几条硬约束：生成器是一次性的，耗尽后再 next 只会抛 StopIteration；

持有文件句柄、锁、网络连接时必须用 try/finally 写清理，并让调用方在提前 break 时显式 `close()` 或用 `contextlib.closing` 包住；

不要在生成器里手动 raise StopIteration（3.7 起 PEP 479 会把它转成 RuntimeError）；生成器管道用 yield from 串联数据源、配合 itertools 可以写出声明式 ETL 流，但每一级都应只做纯变换，副作用与异常处理交给边界层。

`inspect.getgeneratorstate` 能给出 GEN_CREATED / GEN_RUNNING / GEN_SUSPENDED / GEN_CLOSED 四种状态，是排查'卡在哪一步'的直接工具。

<Term word='生成器函数与 yield' text='含 yield 的函数是生成器函数，调用它并不执行函数体，而是返回一个 generator 对象：此时 code object 的 co_flags 含 CO_GENERATOR，gi_frame 已经存在但指令指针停在最开头，inspect.getgeneratorstate 返回 GEN_CREATED。第一次必须' />

<Term word='执行暂停与恢复' text='yield from iterable（PEP 380，3.3+）把产出与接收全部委托给子迭代器：调用方 send 的值会转发到子生成器，子生成器耗尽后的 return 值成为整个 yield from 表达式的结果，throw 与 close 也会沿委托链传下去，省掉手写转发样板。g.throw(exc) 在生成器暂' />


## 带清理的可暂停数据管道：send 调阈值、yield from 串联、close 收尾

一个流式报表生成器逐行读数据、按调用方动态调整的阈值过滤，并把多份数据源用 yield from 串成一条管道。用 send 把新阈值送进生成器，避免为每档阈值重开一次文件；用 yield from 委托给子生成器，让 send / throw / close 自动沿链转发；

最关键的是把文件句柄与计数器的收尾写进 finally，并保证调用方提前退出时显式 `close()`，否则句柄会一直挂到 GC。下面用标准库模拟数据源，演示启动、send 调参、yield from 委托与 close 触发清理这四个动作，并用 inspect 观察状态变化。

重点是把副作用关进 finally，而不是靠调用方记得跑完整个生成器。

```python
from contextlib import closing
import inspect

def source(rows):
    for r in rows:
        yield r
    return 'source done'

def filtering(rows, log):
    threshold = 0
    try:
        label = yield from source(rows)
        while True:
            new = yield label
            if new is None:
                break
            threshold = new
            log.append('threshold ' + str(threshold))
    finally:
        log.append('cleaned')
    return threshold

log = []
with closing(filtering([1, 2, 3], log)) as g:
    print('start', next(g))
    print('send 5', g.send(5))
print('log', log)
print('state', inspect.getgeneratorstate(g))
```

<Callout type="idea" title='落地提示' text='用 yield from 把多个数据源串成管道，配合 itertools 可以写出声明式的 ETL 流' />

<CheckList id='P026b' title='上线前自检' :items='["能复现并解释「生成器持有文件句柄迟迟不释放」", "能复现并解释「把清理逻辑写在 except Exception 里，clo」", "能复现并解释「用 g.send(5) 启动刚创建的生成器抛 TypeErr」", "能用一条命令验证 生成器函数与 yield", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import itertools; print(list(itertools.islice(itertools.count(), 3)))"
```

把输入换成你自己的数据，观察结果是否仍符合 **生成器函数与 yield** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 生成器收尾与自测

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 生成器持有文件句柄迟迟不释放 | 调用方提前 break 后生成器被挂起，没有 close() 就不会执行 finally | 在生成器里用 try/finally 写清理；调用方用 contextlib.closing(g) 或显式 g.close() 收尾 |
| 把清理逻辑写在 except Exception 里，close() 时没执行 | close() 抛的是 GeneratorExit，它继承 BaseException 而不是 Exception | 清理一律放进 finally；except Exception 只处理业务异常，不要承担资源释放 |
| 用 g.send(5) 启动刚创建的生成器抛 TypeError | 刚创建的生成器还没有任何 yield 表达式在等待接收值 | 先 next(g) 或 g.send(None) 启动到第一个 yield，之后才 send 非 None 值 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：生成器持有文件句柄迟迟不释放", "body": "调用方提前 break 后生成器被挂起，没有 close() 就不会执行 finally", "tip": "在生成器里用 try/finally 写清理；调用方用 contextlib.closing(g) 或显式 g.close() 收尾"}, {"title": "第 2 步：把清理逻辑写在 except Excepti", "body": "close() 抛的是 GeneratorExit，它继承 BaseException 而不是 Exception", "tip": "清理一律放进 finally；except Exception 只处理业务异常，不要承担资源释放"}, {"title": "第 3 步：用 g.send(5) 启动刚创建的生成器抛", "body": "刚创建的生成器还没有任何 yield 表达式在等待接收值", "tip": "先 next(g) 或 g.send(None) 启动到第一个 yield，之后才 send 非 None 值"}]' />

<Exercise title='基础：写一个双向通信的累加器生成器' task='实现 accumulator：next 启动产出当前累计值，send(x) 把 x 加进累计并产出新值，send(None) 结束并把总和作为 return 值；用 StopIteration.value 取回。' solution='def accumulator():\n    total = 0\n    while True:\n        v = yield total\n        if v is None:\n            break\n        total += v\n    return total\n\ng = accumulator()\nprint(&#39;prime&#39;, next(g))\nprint(&#39;add 7&#39;, g.send(7), &#39;add 3&#39;, g.send(3))\ntry:\n    g.send(None)\nexcept StopIteration as e:\n    print(&#39;total&#39;, e.value)' explain='yield 是表达式，send 的值成为 v；第一次必须 next 启动。生成器 return 的值写进 StopIteration.value（PEP 380），调用方用 e.value 取回总和 10。' />

<Exercise title='进阶：用 yield from 委托并验证 close 触发 finally' task='写一个子生成器与一个用 yield from 委托的父生成器，验证父生成器的 return 值能被子生成器带回；再对挂起的生成器 close()，确认 finally 执行且状态变 GEN_CLOSED。' solution='import inspect\n\ndef child():\n    yield 1\n    yield 2\n    return &#39;child done&#39;\n\nlog = []\ndef parent():\n    try:\n        result = yield from child()\n        yield result\n    finally:\n        log.append(&#39;cleaned&#39;)\n\ng = parent()\nprint(&#39;values&#39;, next(g), next(g))\nprint(&#39;return via yield from&#39;, next(g))\nh = parent()\nnext(h)\nh.close()\nprint(&#39;cleanup&#39;, log, inspect.getgeneratorstate(h))' explain='yield from 把子生成器的 return 值作为表达式结果带回，并转发 send / throw / close；close 在暂停处抛 GeneratorExit 触发 finally，之后状态为 GEN_CLOSED。清理逻辑只能放进 finally。' />

<Quiz no='026-1' q='调用刚创建的生成器对象时，函数体会怎样？' :options='["立即执行到第一个 yield", "完全不执行，只返回 generator 对象，状态 GEN_CREATED", "执行到 return", "抛 StopIteration"]' answer="1" explain='生成器函数调用只构造 generator 对象，函数体要等第一次 next() / send(None) 才启动；inspect.getgeneratorstate 此时为 GEN_CREATED。' />

<Quiz no='026-2' q='g.close() 在生成器暂停处抛出的是？' :options='["ValueError", "GeneratorExit，继承 BaseException", "StopIteration", "RuntimeError"]' answer="1" explain='close() 注入 GeneratorExit 来触发 finally 清理；它继承 BaseException 而非 Exception，因此 except Exception 拦不住，清理必须写进 finally。' />

<Quiz no='026-3' q='yield from 相比手写 for + yield 多了什么能力？' :options='["只是语法更短", "自动转发 send / throw / close，并接收子生成器的 return 值", "会自动并行", "会物化全部结果"]' answer="1" explain='PEP 380 的 yield from 把产出、send 值、throw 与 close 全部委托给子迭代器，并把子生成器的 return 值（StopIteration.value）作为表达式结果回传。' />

<Predict no='026-P' q='g = accumulator() 后直接 g.send(5) 会怎样？' :options='["正常产出 0", "抛 TypeError: can&#39;t send non-None value to a just-started generator", "返回 5"]' answer='1' output='TypeError: can&#39;t send non-None value to a just-started generator' explain='刚创建的生成器还没有任何 yield 表达式在等待接收值，send 非 None 会抛 TypeError；必须先 next(g) 或 g.send(None) 启动到第一个 yield，之后才能 send 具体值。' />

<FillBlank no='026-F' tpl='___ inspect' :answers='["import"]' hint='回想本讲关于 生成器函数与 yield 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 可暂停的状态机：帧、启动与 send 双向通信 的落点。' />

<KnowledgeCard :points='["含 yield 的函数调用后不执行函数体，只返回 generator；首次必须 next(g) 或 g.send(None) 启动", "yield 是表达式，send(value) 把值作为当前 yield 的返回值；帧里保存局部变量与指令指针实现暂停恢复", "生成器 return value 写入 StopIteration.value（3.3+），yield from 据此回传并转发 send / throw / close", "close() 抛 GeneratorExit（继承 BaseException）触发 finally；清理只能写进 finally，except Exception 拦不住", "3.7 起 PEP 479 把生成器内 StopIteration 转成 RuntimeError；用 return 结束而非手动 raise", "生成器是 async/await 的基座；持有资源时用 try/finally 并让调用方提前退出时显式 close()"]' :pitfalls='["生成器持有文件句柄迟迟不释放", "把清理逻辑写在 except Exception 里，close() 时没执行", "用 g.send(5) 启动刚创建的生成器抛 TypeError", "忘记 close() 会让持有文件句柄的生成器迟迟不释放；在 finally 里写清理逻辑才可靠"]' summary='yield 把函数变成可暂停的状态机：局部变量、指令指针都留在帧里，恢复时从上次位置继续，这正是后来 async/await 的基座' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 含 yield 的函数调用后不执行函数体，只返回 generator；首次必须 next(g) 或 g.send(None) 启动 | 建立直觉 |
| yield 是表达式，send(value) 把值作为当前 yield 的返回值；帧里保存局部变量与指令指针实现暂停恢复 | 跑通示例 |
| 生成器 return value 写入 StopIteration.value（3.3+），yield from 据此回传并转发 send / throw / close | 深入边界 |
| close() 抛 GeneratorExit（继承 BaseException）触发 finally；清理只能写进 finally，except Exception 拦不住 | 工程落地 |
| 3.7 起 PEP 479 把生成器内 StopIteration 转成 RuntimeError；用 return 结束而非手动 raise | 随堂检测 |
| 生成器是 async/await 的基座；持有资源时用 try/finally 并让调用方提前退出时显式 close() | 复盘 |

1. 含 yield 的函数调用后不执行函数体，只返回 generator；首次必须 next(g) 或 g.send(None) 启动

2. yield 是表达式，send(value) 把值作为当前 yield 的返回值；帧里保存局部变量与指令指针实现暂停恢复

3. 生成器 return value 写入 StopIteration.value（3.3+），yield from 据此回传并转发 send / throw / close

[下一讲：阶段综合：词频统计与内存版 KV](/containers/capstone)
