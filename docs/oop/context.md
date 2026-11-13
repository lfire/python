---
title: 第 042 讲 · 上下文管理器与 with 协议
description: 写出异常安全的资源管理代码
---

<StageHeader stage='L4 · 面向对象' level='★★☆☆☆' time='30 分钟' goal='写出异常安全的资源管理代码' prereq='第 041 讲 · 特殊方法：repr、比较、算术与容器协议' />

# 第 042 讲 · 上下文管理器与 with 协议

顺着上一讲的协议视角，with 是看似语法糖、实则有确定规则的入口，也就是上下文管理器。接着处理更日常的事：开文件、连库、加锁，用完都得还回去。

夜间批量任务结束后告警没响，清算事务出错时只关了文件却把半截数据提交了出去，别扭都在「申请」与「释放」没绑在一起。本讲先摊开 __enter__ 与 __exit__ 的三参数、说清返回真值为何抑制异常，再走到 contextlib 的 contextmanager 与 ExitStack，最后用事务、计时收尾。需要阶段一的异常、阶段三的生成器与第 41 讲的特殊方法；学完你能写出异常安全的资源管理代码。


## 一个忘记关闭连接导致事务半提交的事故

一批夜间批量任务结束后，告警系统始终没报出失败：排查发现有人图省事在 `__exit__` 里写了 return True，把所有数据库异常都吞掉了，日志里连一条堆栈都没有。

另一处工单方向相反：清算事务在 with 块里抛错，开发者以为资源会自动回滚，结果 `__exit__` 里只做了 `file.close()`，事务把半截数据 commit 了出去。

还有人用 `contextlib.contextmanager` 写清理逻辑，却在生成器里 yield 了两次，运行时抛 RuntimeError: generator didn't stop；

以及把同步 with 直接套在异步数据库连接上，`__exit__` 里的 await 根本没法执行。with 看起来只是「自动关文件」的语法糖，实际上它是一条带异常分发的协议：`__enter__` 的返回值、`__exit__` 的三个参数、返回值是否抑制异常、以及 LIFO 的组合顺序，每一处都有确定的规则。

本讲把这些规则与 contextlib 的工具逐一对上，并给出事务、计时、动态组合三类场景的正确写法。

<Callout type="warn" title='先看一个真实会出错的写法' text='__exit__ 里随手 return True 吞掉真实异常：返回真值即抑制异常，异常不会传播、traceback 也不记录，日志里只剩「任务成功」' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 041 讲 · 特殊方法：repr、比较、算术与容器协议 |
| 难度 / 建议时长 | ★★☆☆☆ · 30 分钟 |
| 本讲新增 | __enter__ / __exit__、异常三参数与抑制、contextlib.contextmanager |
| 一句话目标 | 写出异常安全的资源管理代码 |
| 为下一讲铺垫 | __slots__、弱引用与对象内存布局 |

<Callout type="tip" title='核心心智模型' text='with EXPR as VAR 的语义由数据模型固定：先求值 EXPR 得到上下文管理器，调用其 __enter__()，把返回值绑定到 VAR（没有 as 则返回值被丢弃），然后执行 with 体；无论体里是否抛异常，最后都调用 __exit__(exc_type, exc_value, tra' />


## with 的展开：__enter__、三参数 __exit__ 与异常抑制

with EXPR as VAR 的语义由数据模型固定：先求值 EXPR 得到上下文管理器，调用其 `__enter__()`，把返回值绑定到 VAR（没有 as 则返回值被丢弃），然后执行 with 体；

无论体里是否抛异常，最后都调用 `__exit__(exc_type, exc_value, traceback)`。

正常结束时三个参数全是 None；体里抛异常时分别是异常类、异常实例、traceback 对象。`__exit__` 返回一个真值（通常是 True）就抑制该异常，异常不会向上传播；返回 False 或 None 则异常继续抛出。

正因如此，「随手 return True」等价于给整段代码加了一个空的 except: pass，是日志里最危险的静默失败源。

需要抑制时也应精确匹配类型，例如只在 exc_type is not None and `issubclass(exc_type, FileNotFoundError)` 时返回 True，其余返回 False 并记录。

还要注意 VAR 绑定的是 `__enter__` 的返回值而非管理器本身：数据库事务常让 `__enter__` 返回 cursor，文件管理器返回文件对象。`__enter__` 里抛异常时 `__exit__` 不会被调用，因为它还没「进入」。

CPython 3.11 起 with 的字节码改由 BEFORE_WITH、WITH_EXCEPT_START 与异常表驱动，替代了 3.10 之前的 SETUP_WITH 块栈，但协议层的三参数语义没变。

```python
class Transaction:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        print('begin', self.name)
        return self
    def __exit__(self, exc_type, exc_value, tb):
        print('exit', exc_type is None, type(exc_value).__name__ if exc_value else 'no-error')
        return False

with Transaction('t1') as t:
    print('body', t.name)
try:
    with Transaction('t2'):
        raise ValueError('boom')
except ValueError as e:
    print('caught', str(e))
```

<OutputBox title='主示例运行结果' output='begin t1\nbody t1\nexit True no-error\nbegin t2\nexit False ValueError\ncaught boom' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Transaction:\n    def __init__(self, name):\n        self.name = name\n    def __enter__(self):\n        print(&#39;begin&#39;, self.name)\n        return self\n    def __exit__(self, exc_type, exc_value, tb):\n        print(&#39;exit&#39;, exc_type is None, type(exc_value).__name__ if exc_value else &#39;no-error&#39;)\n        return False\n\nwith Transaction(&#39;t1&#39;) as t:\n    print(&#39;body&#39;, t.name)\ntry:\n    with Transaction(&#39;t2&#39;):\n        raise ValueError(&#39;boom&#39;)\nexcept ValueError as e:\n    print(&#39;caught&#39;, str(e))' :notes='["自定义上下文管理器，集中演示 __enter__ 与 __exit__ 协议", "构造时保存事务名", "把名字绑到实例属性，with 期间保持有效", "__enter__ 在 with 体执行前调用", "打印进入信息；真实场景在这里申请连接、开启事务", "返回值绑定到 as t，这里返回管理器自身", "__exit__ 固定接收异常类、异常实例、traceback 三个参数", "无异常时 exc_type 为 None，有异常时读出异常类型名", "返回 False 不抑制异常，让它继续向上传播", "正常路径：__enter__ 返回值绑定到 t", "with 体正常执行完毕", "外层 try 用于接住第二段故意抛出的异常", "异常路径：进入第二个 with", "with 体抛 ValueError，触发异常分发", "异常作为三参数传给 __exit__，返回 False 后向外抛", "打印被捕获的消息，证明 return False 没有抑制异常"]' title='第 042 讲 · 上下文管理器与 with 协议' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**with 协议展开与 __exit__ 返回值语义**

| 阶段 | 调用 / 参数 | 返回值作用 | 失效信号 |
| --- | --- | --- | --- |
| 求值 EXPR | 得到上下文管理器对象 | 无 | 对象无 __enter__ 抛 AttributeError |
| 进入 | __enter__() | 绑定到 as VAR；无 as 则丢弃 | __enter__ 抛异常则 __exit__ 不执行 |
| 正常结束 | __exit__(None, None, None) | 真值抑制、False/None 不抑制 | 此时返回 True 无可见效果但易养成坏习惯 |
| 异常结束 | __exit__(exc_type, exc_value, tb) | 返回 True 吞异常，返回 False 继续抛 | return True 会让日志完全没有线索 |
| 3.11 字节码 | BEFORE_WITH / WITH_EXCEPT_START | 异常表驱动零成本处理 | 3.10 及以前是 SETUP_WITH 块栈 |


## contextlib 三件套：contextmanager、ExitStack 与 suppress

`contextlib.contextmanager` 把一个「只 yield 一次」的生成器函数变成上下文管理器：yield 之前的代码对应 `__enter__`，yield 之后的代码对应 `__exit__`，且必须用 try/finally 包住 yield，否则异常路径不会执行清理。

它返回的 _GeneratorContextManager 通过 `generator.throw()` 把异常送回生成器；

若生成器又 yield 了第二个值，会抛 RuntimeError: generator didn't stop after `throw()`。这个对象同时是 ContextDecorator，因此也能当装饰器给整个函数套上下文。

ExitStack（3.3 引入）解决「上下文数量运行时才确定」：`enter_context(cm)` 逐个进入，`callback(fn, *args)` 注册任意清理回调，`push(cm)` 接管实现了 `__exit__` 但没 `__enter__` 的对象；

退出时严格按进入的逆序（LIFO）执行，后进入的先清理。

`contextlib.suppress(*exceptions)` 精确抑制列出的异常类型，比裸 try/except: pass 可读；

`closing(obj)` 对只有 `close()` 的对象适配成上下文；redirect_stdout 临时替换 `sys.stdout`；nullcontext 用于「有时需要上下文、有时不需要」的分支。

异步侧对应 `__aenter__`/`__aexit__` 与 async with，asynccontextmanager（3.7）和 AsyncExitStack（3.7）提供同样的组合能力，`__aexit__` 必须是 async def 才能 await 清理动作。

```python
from contextlib import contextmanager, ExitStack, suppress

@contextmanager
def tag(label):
    print('enter', label)
    try:
        yield label
    finally:
        print('exit', label)

with ExitStack() as stack:
    stack.enter_context(tag('A'))
    stack.enter_context(tag('B'))
    stack.callback(print, 'callback')
    print('body')
with suppress(ZeroDivisionError):
    print(1 / 0)
print('after suppress')
```

<OutputBox title='对照写法：先自己猜，再点开' output='enter A\nenter B\nbody\ncallback\nexit B\nexit A\nafter suppress' guess="true" />

**contextlib 工具、引入版本与适用场景**

| 工具 | 引入版本 | 用途 | 关键约束 |
| --- | --- | --- | --- |
| contextmanager | 2.5 | 生成器转上下文，兼作装饰器 | 必须只 yield 一次并用 try/finally |
| ExitStack | 3.3 | 运行时动态组合多个上下文 | 退出严格 LIFO，后进入先清理 |
| suppress | 3.4 | 精确抑制指定异常类型 | 只列要吞的类型，别用空 except |
| closing | 2.5 | 把只有 close() 的对象适配成上下文 | 对象需实现无参 close |
| asynccontextmanager | 3.7 | async with 的生成器写法 | __aexit__ 必须是 async def |
| AsyncExitStack | 3.7 | 异步上下文的动态组合 | enter_async_context 返回可等待对象 |

<Term word='__enter__ / __exit__' text='with EXPR as VAR 的语义由数据模型固定：先求值 EXPR 得到上下文管理器，调用其 __enter__()，把返回值绑定到 VAR（没有 as 则返回值被丢弃），然后执行 with 体；无论体里是否抛异常，最后都调用 __exit__(exc_type, exc_value, traceback)。正常' />

<Term word='异常三参数与抑制' text='contextlib.contextmanager 把一个「只 yield 一次」的生成器函数变成上下文管理器：yield 之前的代码对应 __enter__，yield 之后的代码对应 __exit__，且必须用 try/finally 包住 yield，否则异常路径不会执行清理。它返回的 _GeneratorCon' />


## 事务与资源场景：把申请与释放写成一段强制配对

上下文管理器最大的工程价值是让「申请—使用—释放」在语法层面强制配对，异常路径和正常路径共用同一份清理代码。

数据库事务是典型：`__enter__` 拿到 cursor 并 BEGIN，`__exit__` 检查 exc_type，为 None 就 commit，否则 rollback，然后 close 并返回 False 让异常继续向上（绝不吞掉）。

计时上下文在 `__enter__` 记 `perf_counter()`，在 finally 里算差值并打点；分布式锁在 `__exit__` 里释放锁并带上 fencing token 校验；

临时目录用 `tempfile.TemporaryDirectory` 已经是一个写好的上下文。

组合多个资源时优先用 ExitStack：它保证逆序释放，避免嵌套 with 越写越深，也避免某个资源申请失败时前面已申请的资源漏掉清理。

写自定义管理器时有一条自检清单：`__exit__` 是否只在有明确理由时返回 True、是否把清理放进 finally、是否对 `__enter__` 失败留有兜底、异步资源是否用了 `__aexit__`。这四点能挡住绝大多数线上静默故障。

CPython 3.11 之前，with 靠块栈实现：SETUP_WITH 把 `__exit__` 与块信息压栈，异常发生时解释器逐层弹出块栈并调用对应清理，正常路径也要执行 WITH_CLEANUP 系列指令，因此无异常也付指令成本。

3.11 起改成异常表（zero-cost exception handling）：co_exceptiontable 记录受保护字节码区间到处理器的跳转，无异常时不执行任何额外指令；

with 用 BEFORE_WITH 取 `__exit__` 并压栈，WITH_EXCEPT_START 在异常路径调用它，若返回真则 POP_TOP 吞掉异常，否则 RERAISE。

contextmanager 生成的对象在 `_GeneratorContextManager.__exit__` 里对生成器调用 `gen.throw(exc_type, exc_value, tb)`；

生成器若在 yield 之后又 yield，则 throw 无法让它终止，抛出 RuntimeError: generator didn't stop after `throw()`。ExitStack 内部维护一个回调栈，退出时 while 循环 pop 并逆序调用，这就是 LIFO 的来源。

三参数与抑制规则的语义在两套实现里保持一致，变的只是异常分发机制。

<Compare :panels='[{"label": "主示例", "code": "class Transaction:\n    def __init__(self, name):\n        self.name = name\n    def __enter__(self):\n        print(&#39;begin&#39;, self.name)\n        return self\n    def __exit__(self, exc_type, exc_value, tb):\n        print(&#39;exit&#39;, exc_type is None, type(exc_value).__name__ if exc_value else &#39;no-error&#39;)\n        return False\n\nwith Transaction(&#39;t1&#39;) as t:\n    print(&#39;body&#39;, t.name)\ntry:\n    with Transaction(&#39;t2&#39;):\n        raise ValueError(&#39;boom&#39;)\nexcept ValueError as e:\n    print(&#39;caught&#39;, str(e))", "note": "with 的展开：__enter__、三参数 __exit__ 与异常抑制"}, {"label": "对照 / 进阶", "code": "from contextlib import contextmanager, ExitStack, suppress\n\n@contextmanager\ndef tag(label):\n    print(&#39;enter&#39;, label)\n    try:\n        yield label\n    finally:\n        print(&#39;exit&#39;, label)\n\nwith ExitStack() as stack:\n    stack.enter_context(tag(&#39;A&#39;))\n    stack.enter_context(tag(&#39;B&#39;))\n    stack.callback(print, &#39;callback&#39;)\n    print(&#39;body&#39;)\nwith suppress(ZeroDivisionError):\n    print(1 / 0)\nprint(&#39;after suppress&#39;)", "note": "contextlib 三件套：contextmanager、ExitStack 与 suppress"}]' title='两种写法对照' note='差异集中在 __enter__ / __exit__；先看输出，再找背后的规则。' />

```python
import sys

class Probe:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        print('exit args:', len(exc), exc[0] is None)
        print('exc_info set:', sys.exc_info()[0] is exc[0])
        return False

print('protocol:', hasattr(Probe, '__enter__'), hasattr(Probe, '__exit__'))
try:
    with Probe():
        raise KeyError('k')
except KeyError:
    print('propagated')
```

<OutputBox title='原理验证' output='protocol: True True\nexit args: 3 False\nexc_info set: True\npropagated' />

**同步与异步上下文协议对照**

| 维度 | 同步 | 异步 |
| --- | --- | --- |
| 进入方法 | __enter__ (普通 def) | __aenter__ (async def) |
| 退出方法 | __exit__ (普通 def) | __aexit__ (async def) |
| 语法 | with EXPR as VAR | async with EXPR as VAR |
| 组合工具 | ExitStack | AsyncExitStack |
| 清理里等待 | 不允许 await | 可以 await 网络关闭与锁释放 |

<ConceptDiagram type='layers3' title='第 042 讲 · 分层视角' labels='with 的展开：__enter__、三|contextlib 三件套：conte|事务与资源场景：把申请与释放写成一段强制|事务与计时场景' caption='事务与资源场景：把申请与释放写成一段强制配对' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **事务与计时场景** 落在哪一层。

<FlowTimeline :steps='[{"title": "with 的展开：__enter__、三参数 __exit__ 与异常抑制", "desc": "with EXPR as VAR 的语义由数据模型固定：先求值 EXPR 得到上下文…", "tone": "blue"}, {"title": "contextlib 三件套：contextmanager、ExitStack 与 suppress", "desc": "contextlib.contextmanager 把一个「只 yield 一次」的…", "tone": "purple"}, {"title": "事务与资源场景：把申请与释放写成一段强制配对", "desc": "上下文管理器最大的工程价值是让「申请—使用—释放」在语法层面强制配对，异常路径和正常…", "tone": "orange"}, {"title": "工程落地", "desc": "用 sqlite3 事务上下文保证异常回滚与成功提交", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 用 sqlite3 事务上下文保证异常回滚与成功提交

账务脚本要在一条事务里先扣款再写明细，任何一步失败都必须整体回滚，否则会出现扣了钱却没记流水。用 try/finally 手写容易漏掉 commit 与 rollback 的分支，也不好复用；把它做成上下文管理器后，申请（拿 cursor）与释放（提交或回滚并关闭）在语法层面强制配对。

下面用标准库 sqlite3 的内存库跑通：`__enter__` 返回 cursor，`__exit__` 依据 exc_type 决定 commit 还是 rollback，并且始终返回 False 让异常继续上抛。第二段 with 正常结束则提交。

SQL 一律用 ? 占位符传参，既避免字符串拼接注入，也把参数化查询的习惯固化进框架雏形。注意 `__exit__` 里没有吞异常，外层仍需自己处理业务错误。

```python
import sqlite3

class Tx:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        self.cur = self.conn.cursor()
        return self.cur
    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cur.close()
        return False

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE acc (id INTEGER PRIMARY KEY, bal INTEGER)')
conn.execute('INSERT INTO acc VALUES (1, 100)')
conn.commit()
try:
    with Tx(conn) as cur:
        cur.execute('UPDATE acc SET bal = bal - 50 WHERE id = 1')
        cur.execute('UPDATE acc SET bal = ? WHERE id = ?', (999, 2))
        raise ValueError('abort')
except ValueError:
    pass
print('bal after rollback:', conn.execute('SELECT bal FROM acc').fetchone()[0])
with Tx(conn) as cur:
    cur.execute('UPDATE acc SET bal = bal + 10 WHERE id = 1')
print('bal after commit:', conn.execute('SELECT bal FROM acc').fetchone()[0])
conn.close()
```

<Callout type="idea" title='落地提示' text='数据库连接、分布式锁、临时目录、指标计时都应做成上下文管理器，让「申请—释放」在语法层面强制配对' />

<CheckList id='P042b' title='上线前自检' :items='["能复现并解释「__exit__ 里随手 return True 吞掉真实异」", "能复现并解释「contextmanager 生成器 yield 了两次或没」", "能复现并解释「在异步代码里用同步 with 管理数据库连接」", "能用一条命令验证 __enter__ / __exit__", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "s='中文'; b=s.encode('utf-8'); print(len(s), len(b), b.hex())"
```

把输入换成你自己的数据，观察结果是否仍符合 **__enter__ / __exit__** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## __exit__ 随手 return True 吞异常的错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| __exit__ 里随手 return True 吞掉真实异常 | 返回真值即抑制异常，异常不会传播、traceback 也不记录，日志里只剩「任务成功」 | 只在明确要吞的异常类型上返回 True（如 issubclass(exc_type, FileNotFoundError)），其余返回 False 并 logging.exception 记录 |
| contextmanager 生成器 yield 了两次或没用 try/finally | 第二次 yield 会让 generator.throw() 无法终止生成器，抛 RuntimeError: generator didn't stop after throw()；没有 finally 则异常路径跳过清理 | 生成器只 yield 一次，并用 try: yield ... finally: 释放资源，把清理放在 finally 里 |
| 在异步代码里用同步 with 管理数据库连接 | __exit__ 是普通 def，里面无法 await 关闭连接；__aexit__ 未定义时 async with 抛 AttributeError: __aenter__ | 改为 __aenter__/__aexit__ 两个 async def 并配合 async with，或用 asynccontextmanager / AsyncExitStack |

<Callout type="warn" title='本讲最容易踩的坑' text='__exit__ 里随手 return True 吞掉真实异常：返回真值即抑制异常，异常不会传播、traceback 也不记录，日志里只剩「任务成功」' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：__exit__ 里随手 return Tr", "body": "返回真值即抑制异常，异常不会传播、traceback 也不记录，日志里只剩「任务成功」", "tip": "只在明确要吞的异常类型上返回 True（如 issubclass(exc_type, FileNotFoundError)），其余返回 False 并 logging.exception 记录"}, {"title": "第 2 步：contextmanager 生成器 yie", "body": "第二次 yield 会让 generator.throw() 无法终止生成器，抛 RuntimeError: generator didn&#39;t stop after throw()；没有 finally 则异常路径跳过清理", "tip": "生成器只 yield 一次，并用 try: yield ... finally: 释放资源，把清理放在 finally 里"}, {"title": "第 3 步：在异步代码里用同步 with 管理数据库连接", "body": "__exit__ 是普通 def，里面无法 await 关闭连接；__aexit__ 未定义时 async with 抛 AttributeError: __aenter__", "tip": "改为 __aenter__/__aexit__ 两个 async def 并配合 async with，或用 asynccontextmanager / AsyncExitStack"}]' />


## 练一练、测一测、记一记

<Exercise title='基础：写异常安全的计时上下文' task='用 contextmanager 写一个 timer(label)，无论 with 体是否抛异常都在 finally 里打印一条固定标记；再用 suppress(ValueError) 包住一个会抛 ValueError 的块，验证异常被抑制且清理仍执行。' solution='from contextlib import contextmanager, suppress\n@contextmanager\ndef timer(label):\n    try:\n        yield\n    finally:\n        print(&#39;cleanup&#39;, label)\nwith suppress(ValueError), timer(&#39;t&#39;):\n    raise ValueError(&#39;x&#39;)\nprint(&#39;done&#39;)' explain='contextmanager 的 finally 保证异常路径也执行清理；suppress 精确吞掉 ValueError，因此程序继续打印 done。若生成器里 yield 第二次会抛 RuntimeError: generator didn&#39;t stop after throw()。' />

<Exercise title='进阶：用 ExitStack 动态组合 N 个文件并验证逆序释放' task='给定运行时才确定的文件数量，用 ExitStack.enter_context 逐个打开并注册 callback 打印关闭标记，验证退出顺序是后进入先释放，并说明一个资源申请失败时前面资源为何不会泄漏。' solution='from contextlib import ExitStack\nlog = []\nclass R:\n    def __init__(self, n): self.n = n\n    def __enter__(self): return self\n    def __exit__(self, *e): log.append(self.n)\nwith ExitStack() as st:\n    for i in range(3):\n        st.enter_context(R(i))\n        st.callback(log.append, &#39;cb&#39; + str(i))\nprint(log)' explain='ExitStack 维护回调栈，退出时 while pop 逆序执行：cb2, 2, cb1, 1, cb0, 0（按注册顺序逆序）。已进入的上下文都在栈里，后续 enter 抛异常时 __exit__ 仍会把栈里已有的全部清理，不会泄漏。' />

<Quiz no='042-1' q='__exit__ 返回 True 会发生什么？' :options='["抑制当前异常，异常不再向上传播", "强制重新抛出异常", "把异常写入 sys.last_value 后继续", "把三个参数改成 None"]' answer="0" explain='__exit__ 返回真值即抑制异常，CPython 3.11 起的 WITH_EXCEPT_START 路径会 POP_TOP 吞掉它；返回 False 或 None 才 RERAISE。随手返回 True 是日志静默的常见根源。' />

<Quiz no='042-2' q='contextlib.contextmanager 的生成器函数必须满足什么？' :options='["只 yield 一次，并把清理放进 try/finally", "yield 至少两次，分别对应进入与退出", "用 return 返回资源而不是 yield", "必须是 async def 生成器"]' answer="0" explain='__exit__ 通过 gen.throw() 把异常送回生成器；再次 yield 会抛 RuntimeError: generator didn&#39;t stop after throw()。try/finally 保证异常路径也执行清理，异步版才需要 async def。' />

<Quiz no='042-3' q='ExitStack 退出多个上下文时的顺序是？' :options='["LIFO，后进入的先清理", "FIFO，先进入的先清理", "按字母序", "随机，取决于 GC"]' answer="0" explain='ExitStack 内部是回调栈，退出时循环 pop 并调用，因此严格逆序。嵌套资源（先连接后加锁）逆序释放才能先解锁再关连接，这与手写嵌套 with 一致。' />

<Predict no='042-P' q='下面 with 块里抛异常且 __exit__ 返回 False，最终输出是什么？' :options='["exit False ValueError / caught boom", "exit True no-error / 无 caught", "exit False ValueError / 抛未捕获异常"]' answer='0' output='exit False ValueError\ncaught boom' explain='异常作为三参数传给 __exit__，exc_type 非 None、exc_value 是 ValueError 实例；返回 False 不抑制，异常被外层 except ValueError 接住并打印 caught boom。' />

<FillBlank no='042-F' tpl='___ __init__(self, name):' :answers='["def"]' hint='回想本讲关于 __enter__ / __exit__ 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 with 的展开：__enter__、三参数 __exit__ 与异常抑制 的落点。' />

<KnowledgeCard :points='["__exit__(exc_type, exc_value, tb) 固定三参数；正常结束全为 None，返回真值抑制异常", "__enter__ 返回值绑定到 as；它抛异常时 __exit__ 不会被调用", "contextmanager 生成器只 yield 一次并配 try/finally；二次 yield 抛 RuntimeError: generator didn&#39;t stop after throw()", "ExitStack 动态组合上下文，退出严格 LIFO；suppress 精确抑制指定异常类型", "事务上下文：exc_type 为 None 则 commit，否则 rollback，且始终返回 False 不吞异常", "异步资源用 __aenter__/__aexit__ 与 async with；3.11 起 with 由异常表而非块栈驱动"]' :pitfalls='["__exit__ 里随手 return True 吞掉真实异常", "contextmanager 生成器 yield 了两次或没用 try/finally", "在异步代码里用同步 with 管理数据库连接", "在 __exit__ 里随手返回 True，会把真正的错误吞掉，日志里什么线索都不留"]' summary='__exit__ 收到异常信息并可选择返回 True 抑制它，这让 with 能同时表达正常与异常两条清理路径' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| __exit__(exc_type, exc_value, tb) 固定三参数；正常结束全为 None，返回真值抑制异常 | 建立直觉 |
| __enter__ 返回值绑定到 as；它抛异常时 __exit__ 不会被调用 | 跑通示例 |
| contextmanager 生成器只 yield 一次并配 try/finally；二次 yield 抛 RuntimeError: generator didn't stop after throw() | 深入边界 |
| ExitStack 动态组合上下文，退出严格 LIFO；suppress 精确抑制指定异常类型 | 工程落地 |
| 事务上下文：exc_type 为 None 则 commit，否则 rollback，且始终返回 False 不吞异常 | 随堂检测 |
| 异步资源用 __aenter__/__aexit__ 与 async with；3.11 起 with 由异常表而非块栈驱动 | 复盘 |

1. __exit__(exc_type, exc_value, tb) 固定三参数；正常结束全为 None，返回真值抑制异常

2. __enter__ 返回值绑定到 as；它抛异常时 __exit__ 不会被调用

3. contextmanager 生成器只 yield 一次并配 try/finally；二次 yield 抛 RuntimeError: generator didn't stop after throw()

[下一讲：__slots__、弱引用与对象内存布局](/oop/slots)
