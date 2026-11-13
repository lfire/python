---
title: 第 015 讲 · 异常：捕获、异常链与自定义异常
description: 建立 EAFP 风格的错误处理直觉
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='30 分钟' goal='建立 EAFP 风格的错误处理直觉' prereq='第 014 讲 · 输入输出与文件初识：print、input、open、with' />

# 第 015 讲 · 异常：捕获、异常链与自定义异常

上一讲让程序能和文件、终端交换数据，可数据一进来就不总按写好的样子出现。这一讲安顿没照预期走的分支，让失败留下痕迹，而不是悄悄改道或停在半途。

设想读配置的小工具把端口转成整数，末尾多个空格时默默用了默认值，格式不对时又卡在启动一半。我们先看清异常层级与捕获边界，再顺着 try 组合、else、finally 与异常链，把补救和资源释放各归其位，也会定义自己的异常基类；末了算一笔开销账，明白异常只配表达意外分支。需要你熟悉变量、条件循环、函数和 with；读完能给小程序划出可观测的失败出口，把底层错误翻成看得懂的提示。


## 配置加载器里两次悄悄失效的默认值

一个配置加载器要把 JSON 里的 port、timeout、retries 转成 int。最初的写法是 LBYL：先用 if 'port' in cfg and str(cfg['port']).`isdigit()` 预检查再转换。

它连着出两次事故：上游把 port 写成 '8080 '，`isdigit()` 返回 False 走了默认值，用户并不知道配置被悄悄改了；另一次写成 '0x50'，预检查通过却在 `int()` 处抛 ValueError 没人接，服务崩在启动一半，已经打开的日志文件与连接都没释放。

更微妙的是预检查和取值之间如果有别的线程改字典，检查结论当场失效。改写成 try: `int(...)` 接 except ValueError 后逻辑短了一半，却又有人为了'别让报错吓到用户'写成 except Exception: pass，把编程错误一起吞掉，排障时只剩一个沉默的服务。

本讲把异常层级、else 与 finally、raise from 异常链、自定义异常基类与 3.11 的异常表拆开，目标是让每个失败分支都有明确、可观测的出口。


## 本讲要建立的失败分支直觉


## 异常层级与 except 的匹配边界

所有异常的根是 BaseException，它的直接子类里只有 Exception 是日常错误的祖先：ValueError、TypeError、KeyError、OSError、ImportError 都挂在 Exception 之下；

而 SystemExit、KeyboardInterrupt、GeneratorExit 与 Exception 平级，同样直接继承 BaseException。

这条分层是有意的：except Exception 故意拦不住 KeyboardInterrupt 与 SystemExit，Ctrl+C 才能中断死循环，`sys.exit()` 才能退出进程。裸 except: 等价于 except BaseException:，会把这三者一并吞下，是最危险的写法。

匹配规则是按 except 子句自上而下逐个检查 `issubclass(实际类型, 指定类型)`，命中第一个就执行、其余不再看，所以子类分支必须写在父类之前，否则永远不可达。

可以用元组 except (TypeError, ValueError) as e: 合并多个类型，as e 绑定的名字在块结束时会被自动删除，避免异常对象经 traceback 延长一批局部变量的生命周期。

自定义异常应继承 Exception 或更具体的内置子类，绝不要继承 BaseException，否则调用方的 except Exception 拦不住它。

3.11 起 PEP 654 还引入 ExceptionGroup / BaseExceptionGroup 与 except*，专门处理并发批量任务里同时抛出的多个异常，普通 except 只能拿到整组、无法按类型拆开处理。

```python
class ConfigError(Exception):
    def __init__(self, key, reason):
        super().__init__(key, reason)
        self.key = key

def read_port(cfg):
    try:
        return int(cfg['port'])
    except KeyError:
        return 8080
    except ValueError as e:
        raise ConfigError('port', 'not an integer') from e

print(read_port({'port': '9090'}), read_port({}))
try:
    read_port({'port': 'abc'})
except ConfigError as e:
    print(type(e).__name__, e.args, e.key)
    print(type(e.__cause__).__name__, e.__suppress_context__)
print(issubclass(KeyboardInterrupt, Exception), issubclass(SystemExit, Exception))
```

<OutputBox title='主示例运行结果' output='9090 8080\nConfigError (&#39;port&#39;, &#39;not an integer&#39;) port\nValueError True\nFalse False' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class ConfigError(Exception):\n    def __init__(self, key, reason):\n        super().__init__(key, reason)\n        self.key = key\n\ndef read_port(cfg):\n    try:\n        return int(cfg[&#39;port&#39;])\n    except KeyError:\n        return 8080\n    except ValueError as e:\n        raise ConfigError(&#39;port&#39;, &#39;not an integer&#39;) from e\n\nprint(read_port({&#39;port&#39;: &#39;9090&#39;}), read_port({}))\ntry:\n    read_port({&#39;port&#39;: &#39;abc&#39;})\nexcept ConfigError as e:\n    print(type(e).__name__, e.args, e.key)\n    print(type(e.__cause__).__name__, e.__suppress_context__)\nprint(issubclass(KeyboardInterrupt, Exception), issubclass(SystemExit, Exception))' :notes='["定义自定义异常，继承 Exception 而不是 BaseException，保证 except Exception 能拦住", "构造器接收出错的键与原因两个业务字段", "调用父类构造器把 (key, reason) 存进 args，str(e) 才有内容", "把 key 额外挂到实例上，边界层可直接读取做日志字段", "read_port 演示 EAFP：不做预检查，直接取值并转换", "try 只包住可能出错的两步，正常路径零成本", "int(cfg[&#39;port&#39;]) 同时可能抛 KeyError（缺键）与 ValueError（格式错）", "缺键属于预期情况，返回默认端口 8080", "except 命中后不再检查后续子句，本分支直接 return", "捕获转换失败，并把底层错误包装成业务异常", "raise ... from e 设置 __cause__ 为这个 ValueError，traceback 显示直接原因", "分别验证：正常转换与缺键默认值", "触发 ValueError 分支，验证包装后的异常形态", "只捕获自定义异常，裸 except 与 except Exception 都不要写", "打印类型、args 元组与自定义字段；args 来自 super().__init__", "__cause__ 是 ValueError，__suppress_context__ 因 from 被置 True", "KeyboardInterrupt 与 SystemExit 都直接继承 BaseException", "两者都不是 Exception 子类，故 except Exception 捕获不到它们"]' title='第 015 讲 · 异常：捕获、异常链与自定义异常' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='flow3' title='第 015 讲 · 异常层级与 except 的匹配边界' labels='异常层级与 except 的匹配边界|else / finally 与 raise|EAFP / LBYL 与异常的性能账' caption='建立 EAFP 风格的错误处理直觉' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 裸 except 为什么会连 Ctrl+C 一起吞掉

**异常层级与捕获边界**

| 写法 | 能捕获的类型 | 关键约束 |
| --- | --- | --- |
| except ValueError: | ValueError 及其子类 | 只处理单一错误，其它异常继续上抛 |
| except (TypeError, ValueError) as e: | 元组中任一类型及子类 | 子类必须写在父类前面，否则子类分支不可达 |
| except Exception as e: | 所有 Exception 子类 | 捕获不到 KeyboardInterrupt / SystemExit / GeneratorExit |
| except: 裸 except | 所有 BaseException 子类 | 连 Ctrl+C 与 sys.exit 一起吞掉，最危险 |
| except* ValueError: (3.11+) | ExceptionGroup 内的 ValueError 成员 | 仅用于 PEP 654 分组异常，普通异常不适用 |


## else / finally 与 raise from 的异常链

try 之后可以跟 except、else、finally 三类子句。else 只在 try 块没有抛异常时执行，用途是把'正常路径的后续'与'可能出错的语句'分开，避免把本不该被 except 捕获的代码塞进 try 里被误吞。

finally 在正常、异常、return、break、continue 各条退出路径上都会执行，唯一例外是 `os._exit`、进程被 SIGKILL 或掉电，因此它是释放文件句柄、锁、连接的唯一可靠位置；

但 finally 里一旦出现 return 或 break，就会替换掉 try 的返回值并静默丢弃正在传播的异常对象，这类 bug 极隐蔽。raise 单独使用是重新抛出当前正在处理的异常。

raise X from Y 把新异常的 `__cause__` 设为 Y，打印 traceback 时显示 The above exception was the direct cause of...；

在 except 块内直接 raise X 而不写 from 时，解释器自动把当前处理的异常记入 `__context__`，显示 During handling of the above exception...。

raise X from None 则把 `__cause__` 设为 None 并把 `__suppress_context__` 置为 True，用来屏蔽底层细节、只暴露业务异常。

`sys.exc_info()` 返回 (type, value, traceback) 三元组，traceback 节点上有 tb_frame、tb_lineno 与 tb_next 可逐帧回溯。

```python
def swallow(flag):
    try:
        if flag:
            return 'from-try'
        raise ZeroDivisionError
    except ZeroDivisionError:
        return 'from-except'
    finally:
        return 'from-finally'

def clean(flag):
    try:
        value = int(flag)
    except ValueError:
        return 'bad'
    else:
        return value * 2
    finally:
        log.append('done')

log = []
print(swallow(True), swallow(False))
print(clean('3'), clean('x'), log)
```

<OutputBox title='对照写法：先自己猜，再点开' output='from-finally from-finally\n6 bad [&#39;done&#39;, &#39;done&#39;]' guess="true" />


### __cause__ 与 __context__ 怎么串起失败原因


## EAFP / LBYL 与异常的性能账

EAFP（Easier to Ask for Forgiveness than Permission）是'先做、失败再补救'，LBYL（Look Before You Leap）是'先检查再做'。Python 偏向 EAFP 有三条硬理由。

其一，try 块在正常路径上几乎不付成本：3.11 之前只多出 SETUP_FINALLY / SETUP_EXCEPT 之类少量字节码，3.11 起 CPython 改用编译器生成的异常表 co_exceptiontable，把每条指令属于哪个 try 范围、抛异常时跳到哪个 handler 全部静态编码，正常执行完全不进运行时栈，这就是'零成本异常'。

其二，LBYL 的检查与操作之间存在 TOCTOU 竞态，文件是否存在、字典键是否还在、值类型是否变化，都可能在两步之间被别的线程改掉。其三，很多'能不能做'根本无法静态判断，检查逻辑本身会重复甚至写错，例如 `str.isdigit()` 对全角数字、正负号、小数点给出的结论与 `int()` 并不一致。

代价是异常真正抛出的路径很贵：要构造 traceback 并逐帧展开，所以异常只该表达 exceptional 分支，不能拿它做常规循环控制。

工程分层上，底层库定义自己的异常基类（如 class `StoreError(Exception)`），边界层统一把异常翻译成错误码、日志与用户提示；

finally 里只放资源释放，不放业务判断。


## 异常表 co_exceptiontable：正常路径的零成本从哪来

CPython 里异常本身是一个对象，根为 BaseException；

每个实例持有 args 元组、`__traceback__`（链表式 traceback 对象）、`__cause__` / `__context__` / `__suppress_context__`。

抛出时 ceval 不是简单跳转，而是把异常对象存进线程状态的 curexc 字段，再沿帧栈逐层查找能处理它的 handler：3.11 之前靠运行时压入的 block stack（SETUP_FINALLY / SETUP_EXCEPT），3.11 起改用编译器生成的异常表——code object 的 co_exceptiontable 是一段紧凑编码，记录每条指令属于哪个 try 范围以及抛异常时该跳到哪个 handler。

这样正常路径完全不需要额外指令，是'零成本异常'的由来；代价是异常真的发生时才查表并逐帧展开，为每帧构造一个含 tb_frame / tb_lineno / tb_next 的 traceback 节点。

finally 的'总执行'由编译器把清理代码块复制到每条退出路径（正常、return、异常）来保证，所以 finally 里再写 return 就会生成新的 RETURN_VALUE、替换原返回值并把异常对象丢掉。

raise ... from 则在异常对象上写 cause 字段并置 `__suppress_context__`，打印器据此选择 direct cause 还是 during handling 文案。


## 配置加载：EAFP 解析、异常链与边界层统一降级

把这个配置读取拆成三层：底层 parse_config 直接做类型转换（EAFP），把 KeyError 与 ValueError 用 raise ... from e 包装成 ConfigError 并保留原始原因；中间层不加 try，让异常自然上抛；

边界层 load_or_default 捕获 ConfigError 与 OSError，用 logging 把 `e.key` 与 `__cause__` 写进日志，再返回一份安全默认配置，保证服务即使配置写错也能带降级参数启动。

with `open(...)` 负责在异常路径上照样关闭文件描述符，finally 那样的资源释放交给上下文管理器而不写业务逻辑。这样单元测试可以直接对 parse_config 断言异常类型与 `e.key`，不必造临时文件、也不必解析日志文本；库代码定义自己的异常基类，边界层是唯一把异常翻译成日志与错误码的地方。

真实项目再把每一步耗时与 trace_id 打进日志即可，核心边界在这三层里已经定死。

```python
import json, logging, os, tempfile

logging.basicConfig(level=logging.ERROR, format='%(levelname)s %(message)s')

class ConfigError(Exception):
    def __init__(self, key, reason):
        super().__init__(key, reason)
        self.key = key

def parse_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    try:
        port = int(raw['port'])
        timeout = float(raw['timeout'])
    except KeyError as e:
        raise ConfigError(e.args[0], 'missing key') from e
    except ValueError as e:
        raise ConfigError('port/timeout', 'not numeric') from e
    if not (0 < port < 65536):
        raise ConfigError('port', 'out of range')
    return {'port': port, 'timeout': timeout}

DEFAULTS = {'port': 8080, 'timeout': 3.0}

def load_or_default(path):
    try:
        return parse_config(path)
    except (ConfigError, OSError) as e:
        logging.error('config fallback key=%s cause=%s', getattr(e, 'key', '-'), getattr(e, '__cause__', None))
        return dict(DEFAULTS)

p = os.path.join(tempfile.gettempdir(), 'depth15.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump({'port': 'abc', 'timeout': '2.5'}, f)
print(load_or_default(p))
os.remove(p)
```

<Callout type="idea" title='落地提示' text='库代码定义自己的异常基类，边界层统一转成错误码与日志；finally 只做资源释放，不放业务逻辑' />


## 错因速查与排查顺序


## 把失败分支练成肌肉记忆

<Exercise title='基础：把 LBYL 改写成 EAFP 并保留原因' task='给定 to_positive(s) 要把字符串转成正整数，现有写法先用 isdigit() 预检查再 int()。改写成 try/except，对非数字抛带 __cause__ 的自定义异常，并用 co_exceptiontable 说明正常路径没有额外指令。' solution='class NumError(Exception):\n    pass\n\ndef to_positive(s):\n    try:\n        v = int(s)\n    except ValueError as e:\n        raise NumError(&#39;not an integer: &#39; + s) from e\n    if v &lt;= 0:\n        raise NumError(&#39;must be positive&#39;)\n    return v\n\nfor s in (&#39;12&#39;, &#39;-3&#39;, &#39;x&#39;):\n    try:\n        print(s, &#39;-&gt;&#39;, to_positive(s))\n    except NumError as e:\n        print(s, &#39;-&gt;&#39;, type(e).__name__, type(e.__cause__).__name__ if e.__cause__ else None)\nprint(&#39;exceptiontable&#39;, len(to_positive.__code__.co_exceptiontable) &gt; 0)' explain='EAFP 把转换与校验收敛到一处，isdigit() 对全角数字与负号判断不一致的问题消失；raise from 让 cause 保留原始 ValueError，边界层可分别记录。3.11+ 的 co_exceptiontable 说明 try 在正常路径不产生运行时指令。' />

<Exercise title='进阶：给并发批量任务写 ExceptionGroup 处理 (3.11+)' task='用 ExceptionGroup 收集三个转换错误，写 except* 分别处理 ValueError 与 KeyError，并说明为什么普通 except 无法按类型拆分组内成员。' solution='def run(items):\n    errs = []\n    for it in items:\n        try:\n            if it.startswith(&#39;k&#39;):\n                raise KeyError(it)\n            int(it)\n        except (ValueError, KeyError) as e:\n            errs.append(e)\n    if errs:\n        raise ExceptionGroup(&#39;batch failed&#39;, errs)\n\ntry:\n    run([&#39;1&#39;, &#39;kx&#39;, &#39;y&#39;])\nexcept* ValueError as g:\n    print(&#39;value errors&#39;, len(g.exceptions))\nexcept* KeyError as g:\n    print(&#39;key errors&#39;, len(g.exceptions))' explain='PEP 654 的 ExceptionGroup 让并发批量任务里的多个失败同时保留；except* 按类型把组分裂成子组，每个子句只看到自己匹配的成员，普通 except ExceptionGroup 只能拿到整组。3.11 之前没有这个语法。' />

<Quiz no='015-1' q='下列哪个异常不会被 except Exception as e: 捕获？' :options='["ValueError", "KeyboardInterrupt", "KeyError", "OSError"]' answer="1" explain='KeyboardInterrupt 与 SystemExit、GeneratorExit 一样直接继承 BaseException，只有裸 except 或 except BaseException 才会捕获它；ValueError / KeyError / OSError 都在 Exception 之下。' />

<Quiz no='015-2' q='关于 finally 中的 return，哪个结论正确？' :options='["finally 的 return 会被忽略", "它会覆盖 try 的返回值并吞掉正在传播的异常", "会与 try 的 return 合并成元组", "仅当 try 抛异常时才生效"]' answer="1" explain='编译器把 finally 的清理代码复制到每条退出路径；finally 里的 return 生成新的 RETURN_VALUE，替换原返回值并把异常对象丢弃，故障因此静默。' />

<Quiz no='015-3' q='raise ConfigError(&#39;x&#39;) from e 之后，异常对象上哪个字段被设置？' :options='["__context__ 为 None 且 __cause__ 为 e", "__cause__ 为 e、__suppress_context__ 为 True", "只有 __traceback__ 变化", "__suppress_context__ 为 False"]' answer="1" explain='from 显式指定 cause，CPython 同时把 __suppress_context__ 置 True，traceback 打印 direct cause 而非 during handling；__context__ 仍会被设为当前正在处理的异常。' />

<Predict no='015-P' q='执行 try: int(&#39;x&#39;) 接 except ValueError: raise KeyError(&#39;k&#39;) 后，捕获到的 KeyError 上 type(e.__context__).__name__、e.__cause__、e.__suppress_context__ 依次是？' :options='["ValueError None False", "ValueError ValueError True", "KeyError None False"]' answer='0' output='ValueError None False' explain='except 块内直接 raise 新异常且不写 from 时，CPython 自动把当前处理的异常记入 __context__，__cause__ 保持 None、__suppress_context__ 保持 False，因此 traceback 会打印 During handling of the above exception。' />

<FillBlank no='015-F' tpl='___ __init__(self, key, reason):' :answers='["def"]' hint='回想本讲关于 异常层级与 BaseException 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 异常层级与 except 的匹配边界 的落点。' />

<KnowledgeCard :points='["BaseException 的直接子类 SystemExit / KeyboardInterrupt / GeneratorExit 不在 Exception 之下，except Exception 拦不住", "异常匹配按 except 子句自上而下，子类必须写在父类前面；as e 绑定的名字在块结束时被删除", "else 只在 try 无异常时执行；finally 总执行，但其中的 return 会覆盖返回值并吞掉异常", "raise X from Y 设 __cause__ 并置 __suppress_context__ 为 True；raise X from None 隐藏底层原因", "3.11 起用 co_exceptiontable 实现零成本异常，正常路径无 SETUP_FINALLY，开销集中在抛出的帧展开", "库定义自己的 Exception 子类，边界层统一转错误码与日志；finally 只放资源释放"]' :pitfalls='["Ctrl+C 杀不掉脚本，sys.exit() 也不退出", "finally 里写了 return，异常凭空消失", "自定义异常用 except Exception 拦不住", "用裸 except 或 except Exception 吞掉一切，会把键盘中断与编程错误一起藏起来，排障时只剩一个沉默的系统"]' summary='Python 鼓励先做再补救（EAFP）：异常在正常路径上几乎零成本，而层层预检查既慢又容易有竞态' />

1. BaseException 的直接子类 SystemExit / KeyboardInterrupt / GeneratorExit 不在 Exception 之下，except Exception 拦不住

2. 异常匹配按 except 子句自上而下，子类必须写在父类前面；as e 绑定的名字在块结束时被删除

3. else 只在 try 无异常时执行；finally 总执行，但其中的 return 会覆盖返回值并吞掉异常

[下一讲：阶段综合：交互式命令行计算器](/foundation/capstone)
