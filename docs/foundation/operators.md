---
title: 第 011 讲 · 运算符与表达式：优先级、短路与真值
description: 能准确预测复杂表达式的结果
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='25 分钟' goal='能准确预测复杂表达式的结果' prereq='第 010 讲 · 字符串操作：切片、f-string 与常用方法' />

# 第 011 讲 · 运算符与表达式：优先级、短路与真值

会算单个数、会截一段文本，自然想把好几个判断连成一行。表达式一长，结果常和心里想的不一样，这一讲就来把运算符与表达式这笔账算准。有个常见的坑：给可能没值的变量兜底，写 `value or default`，合法的 0 或空列表也被换掉；`-7 // 2` 的商余，符号也和直觉对不上。我们先把算术与整除、比较链理顺；再看 and 与 or 的布尔短路与返回值、顺带说海象运算符；最后落到真值测试背后，`__bool__` 与 `__len__` 怎样决定 if 走哪支。熟悉变量、数值类型和布尔判断就够；学完你能预测复杂表达式，也写得出不误伤假值的兜底。


## and / or 返回的不是布尔值：短路拿到的是操作数

一个配置读取函数用 `cfg.get('timeout') or 30` 给超时兜底，本意是「没配就用 30 秒」，结果运维明确把 timeout 配成 0（表示不超时）时，程序却悄悄用了 30，线上该快速失败的请求反而挂住 30 秒。

另一处判断写 `if result and result.ok:`，当 result 是空列表时整段被跳过，连日志都没有；

还有人把 and / or 当成返回布尔值的逻辑运算，写 `flag = a and b` 后直接拿 flag 去做加法，得到的是某个操作数而不是 True 或 False。

朴素解法是「多写几个 if 判一下」或「把 0 当非法值过滤掉」，两者都误判了 or 的真实语义：它返回决定结果的那个操作数，0、空串、空容器都是合法的假值，不该被兜底替换。本讲把整除与取模的规则、比较链、短路返回值、海象运算符、真值测试协议讲清，让复杂表达式的结果能准确预测。


## 算术、整除与比较链：结果的符号不是凭直觉

算术里最容易错的是整除 // 与取模 % 对负数的处理。// 是向下取整（floor），不是向零截断：`-7 // 2` 得 -4 而不是 -3，`7 // 2` 得 3；

% 的结果与除数同号，且商 q 与余数 r 恒满足 `a == q * b + r`，所以 `-7 % 2` 得 1（因为 -4 乘 2 加 1 等于 -7）。`divmod(a, b)` 一次返回商与余数组成的二元组，比分开算少一次除法且保证一致；

float 参与时结果变浮点，还要注意 b 为 0 抛 ZeroDivisionError。幂运算 ** 是右结合：`2 ** 3 ** 2` 等于 `2 ** 9` 得 512，不是 64。

比较链 `1 < 2 < 3` 不是先算 1 < 2 再拿布尔值和 3 比，而是等价于 `1 < 2 and 2 < 3`，中间操作数只求值一次；

`1 < 3 < 2` 因此为 False。比较运算符可重载（`__lt__`、`__eq__` 等），is 与 in 不在同一套协议里。优先级从高到低大致是 **、正负号、乘除与整除取模、加减、比较、not、and、or，记不清时用括号显式分组，比依赖记忆可靠。

```python
print('or_value', 0 or 0.0 or 'default')
print('and_value', 1 and 2 and 3)
print('and_short', 0 and (1 / 0))
print('floordiv', -7 // 2, 7 // 2)
print('mod', -7 % 2)
print('chain', 1 < 2 < 3, 1 < 3 < 2)
print('divmod', divmod(7, 2))
```

<OutputBox title='主示例运行结果' output='or_value default\nand_value 3\nand_short 0\nfloordiv -4 3\nmod 1\nchain True False\ndivmod (3, 1)' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='print(&#39;or_value&#39;, 0 or 0.0 or &#39;default&#39;)\nprint(&#39;and_value&#39;, 1 and 2 and 3)\nprint(&#39;and_short&#39;, 0 and (1 / 0))\nprint(&#39;floordiv&#39;, -7 // 2, 7 // 2)\nprint(&#39;mod&#39;, -7 % 2)\nprint(&#39;chain&#39;, 1 &lt; 2 &lt; 3, 1 &lt; 3 &lt; 2)\nprint(&#39;divmod&#39;, divmod(7, 2))' :notes='["or 从左到右返回第一个真值操作数，0 与 0.0 都是假值", "and 全部为真时返回最后一个操作数 3，而不是 True", "0 为假使 and 短路，右侧 1 / 0 未执行，返回 0", "整除向下取整：-7 // 2 得 -4，而 7 // 2 得 3", "余数与除数同号，-7 % 2 得 1，满足整除恒等式", "比较链等价于 and 串联，中间值只求值一次", "divmod 一次返回商与余数组成的二元组"]' title='第 011 讲 · 运算符与表达式：优先级、短路与真值' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**整除与取模的符号规则**

| 表达式 | 结果 | 依据 |
| --- | --- | --- |
| 7 // 2 | 3 | 向下取整 |
| -7 // 2 | -4 | floor 向负无穷，不是向零截断 |
| -7 % 2 | 1 | 与除数同号，满足 a == (a//b)*b + a%b |
| divmod(7, 2) | (3, 1) | 一次除法返回商与余数 |
| 2 ** 3 ** 2 | 512 | 幂运算右结合，先算 3 ** 2 |


## and / or 返回操作数：短路与兜底陷阱

and 与 or 返回的是决定结果的那个操作数，不是布尔值：`1 and 2 and 3` 得 3（全部为真，返回最后一个），`0 or 0.0 or 'default'` 得 'default'（前面都是假值，返回第一个真值），`0 or []` 得 []。

求值顺序从左到右且短路：`a and b` 在 a 为假时直接返回 a、不再求值 b；`a or b` 在 a 为真时直接返回 a。

这个特性让 `x = a or default` 这种默认值写法简洁，却也埋了坑：当 a 可能是 0、0.0、空字符串、空容器这些合法假值时，会被悄悄替换成 default。

正确写法是显式判断 `a is None` 时再用默认值，或用条件表达式 `default if a is None else a` 把「只在缺失时兜底」写清楚。

短路还是「避免异常」的常用手段：`0 and (1 // 0)` 得 0，右侧的除零根本没执行；但别把它当错误处理机制滥用，意图不明时不如把 if 写清楚。

海象运算符 :=（3.8 起）在表达式内部赋值并返回值，`if (n := len(data)) > 2:` 能避免重复调用 len；

它必须用括号包住，且不能出现在推导式最外层迭代变量等受限位置。

```python
data = [1, 2, 3]
if (n := len(data)) > 2:
    print('walrus_n', n)

count = 0
print('or_bug', count or 'fallback')
print('fixed', count if count is not None else 'fallback')
print('truthy_empty', bool([]), bool(''), bool(0))
print('nonzero', bool([0]), bool('0'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='walrus_n 3\nor_bug fallback\nfixed 0\ntruthy_empty False False False\nnonzero True True' guess="true" />


## 真值测试协议：__bool__ 与 __len__ 如何决定 if

任何对象都能放进 if 或 `bool()`，判定规则是：先查类型是否实现 `__bool__`，有则用它返回的布尔值；没有 `__bool__` 再查 `__len__`，长度为 0 视为假、非零视为真；两者都没有的对象恒为真。

内置的假值包括 None、False、数值零（0、0.0、0j）、空容器与空序列（空串、空 list、空 dict、空 tuple、空 set）以及 `range(0)`；自定义容器若忘了实现 `__bool__` 或 `__len__`，实例恒为真，即使内部是空的，if obj 的判断就会违反直觉。

注意 `bool([0])` 为 True（列表非空），`bool('0')` 也为 True（非空字符串），真值看的是容器或序列本身而非元素。

运算符重载的入口是双下方法：`__add__` 对应 +、`__iadd__` 对应 +=、`__eq__` 对应 ==、`__lt__` 对应 <，而 and 与 or 没有对应的重载钩子（它们由解释器按操作数真值短路，不调用 `__and__`；`__and__` 是位与 & 的入口，别混淆）。

理解真值协议，才能解释为什么给自定义集合实现 `__len__` 后 if obj 突然开始按空与非空分支，以及为什么 or 兜底会把 0 当成没值。


## 用 or 兜底为什么会吃掉合法的 0

`timeout=0` 这类合法配置写成 x or default 会被换掉，因为 or 只认真值、不分「缺失」与「配了假值」。

`dict.get(k, default)` 只在键缺失时兜底，值为 0 时原样返回，这是关键；

显式写 value is None 再兜底，或 value if value is not None else default。`bool(0)` 假而 `bool('0')` 真，数值零与空容器最易踩坑；只实现 `__len__` 返回 0 的对象也会被吞。下面的模型把三态分开，术语卡收「真值」「缺失」。

<Callout type="tip" title='核心心智模型' text='算术里最容易错的是整除 // 与取模 % 对负数的处理。// 是向下取整（floor），不是向零截断：`-7 // 2` 得 -4 而不是 -3，`7 // 2` 得 3；% 的结果与除数同号，且商 q 与余数 r 恒满足 `a == q * b + r`，所以 `-7 % 2` 得 1（因为 -4' />

<Term word='算术与整除' text='算术里最容易错的是整除 // 与取模 % 对负数的处理。// 是向下取整（floor），不是向零截断：`-7 // 2` 得 -4 而不是 -3，`7 // 2` 得 3；% 的结果与除数同号，且商 q 与余数 r 恒满足 `a == q * b + r`，所以 `-7 % 2` 得 1（因为 -4 乘 2 加 1 等' />

<Term word='比较链' text='and 与 or 返回的是决定结果的那个操作数，不是布尔值：`1 and 2 and 3` 得 3（全部为真，返回最后一个），`0 or 0.0 or &#39;default&#39;` 得 &#39;default&#39;（前面都是假值，返回第一个真值），`0 or []` 得 []。求值顺序从左到右且短路：`a and b` 在 a 为假时直' />


## 真值判断的底层：__bool__、__len__ 与 __and__ 的分工

and 与 or 在 CPython 里编译成 `JUMP_IF_FALSE_OR_POP`、`JUMP_IF_TRUE_OR_POP` 一类的跳转指令：先把左操作数压栈并复制一份做真值测试，若结果已由它决定，就直接把这份值留在栈顶、跳过右操作数的字节码块，否则弹出该副本继续求值右侧。

正因为栈顶留的是原对象而不是 `bool()` 的结果，返回值才是操作数本身。真值测试由 PyObject_IsTrue 统一处理：先查类型的 nb_bool 槽位（对应 `__bool__`），没有则查长度协议（对应 `__len__`），再没有就返回真。

整除与取模由 long_divmod 实现，先按 floor 取整得到商 q，再用 a 减去 q 乘 b 反算余数 r，因此余数符号跟随除数 b，恒等式 `a == q * b + r` 始终成立，这就是为什么 `-7 // 2` 是 -4 而 `-7 % 2` 是 1。

比较链则由编译器改写成带复制栈顶与条件跳转的 and 序列，让中间操作数只求值一次。

<ConceptDiagram type='flow4' title='第 011 讲 · 算术、整除与比较链：结果的符号不是凭直觉' labels='算术、整除与比较链：结果的符号不是凭直觉|and / or 返回操作数：短路与兜底陷阱|真值测试协议：__bool__ 与 __le' caption='能准确预测复杂表达式的结果' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 配置解析：区分「没配」与「配了合法假值」

一个服务从配置中心读取超时、重试次数与开关，早期对每个配置都写成 `cfg.get(k) or default` 一路兜底，结果运维把 timeout 配成 0（不超时）、retries 配成 0（不重试）时全被替换成默认，行为与配置完全相反；

还有把 `flag and flag.value` 的结果直接当布尔用，拿到的是字符串。

下面这段给出工程写法：用 `is None` 精确区分「没配」与「配了合法假值」，用海象运算符避免重复读取，用显式 `bool()` 把真值协议的结果收敛成布尔，用比较链与 divmod 做范围与整除校验。真实系统还应把解析结果封成带类型的数据类，但边界处的判断原则不变：不要用一个 or 吞掉所有假值。

```python
def read_int(cfg, key, default):
    raw = cfg.get(key)
    return default if raw is None else int(raw)

def read_bool(cfg, key, default):
    raw = cfg.get(key)
    return default if raw is None else bool(raw)

def in_range(value, lo, hi):
    return lo <= value <= hi

cfg = {'timeout': 0, 'retries': 0, 'enabled': ''}
timeout = read_int(cfg, 'timeout', 30)
retries = read_int(cfg, 'retries', 3)
enabled = read_bool(cfg, 'enabled', True)
print('timeout', timeout, 'in_range', in_range(timeout, 0, 60))
print('retries', retries)
print('enabled', enabled)
if (n := len(cfg)) >= 3:
    print('keys', n)
q, r = divmod(timeout, 7)
print('divmod', q, r)
```

<Callout type="idea" title='落地提示' text='真值测试依赖 __bool__ / __len__，自定义容器要正确实现，否则 if obj 的判断会违反直觉' />


## 短路与兜底的错因速查

短路类 bug 不报错，只能靠返回值和副作用反推。先确认拿的是操作数还是布尔：a or b 返回决定结果的值，要布尔套 `bool()`；也别把 `__and__` 当 and 的重载，它是位与 & 的入口，and/or 由解释器按真值短路、不调双下方法。0 and (1//0) 不抛异常正是右侧未求值的证据。

自定义容器缺 `__bool__` 或 `__len__` 时 if obj 恒真；

`getattr(obj, 'x', None)` or 默认值也会吃 0。

下表按现象、根因、写法列成速查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 or 给可能为 0 或空容器的值兜底 | or 返回决定结果的操作数，0、空串、空容器都是合法假值，会被当成没值悄悄替换成默认值 | 显式判断 value is None 再用默认值，或用 value if value is not None else default |
| 以为 and/or 返回布尔值，或把 __and__ 当成 and 的重载 | 它们返回操作数且按真值短路，不调用 __and__；__and__ 是位与 & 的入口 | 需要布尔结果时用 bool(a and b)；需要位运算时明确写 & |
| 自定义容器不实现 __bool__ 或 __len__ 就放进 if | 两者都没有的对象恒为真，空容器也会走进非空分支且无报错 | 实现 __len__ 返回元素个数，或实现 __bool__ 明确表达空与非空 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 or 给可能为 0 或空容器的值兜底：or 返回决定结果的操作数，0、空串、空容器都是合法假值，会被当成没值悄悄替换成默认值' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 or 给可能为 0 或空容器的值兜底", "body": "or 返回决定结果的操作数，0、空串、空容器都是合法假值，会被当成没值悄悄替换成默认值", "tip": "显式判断 value is None 再用默认值，或用 value if value is not None else default"}, {"title": "第 2 步：以为 and/or 返回布尔值，或把 __a", "body": "它们返回操作数且按真值短路，不调用 __and__；__and__ 是位与 &amp; 的入口", "tip": "需要布尔结果时用 bool(a and b)；需要位运算时明确写 &amp;"}, {"title": "第 3 步：自定义容器不实现 __bool__ 或 __", "body": "两者都没有的对象恒为真，空容器也会走进非空分支且无报错", "tip": "实现 __len__ 返回元素个数，或实现 __bool__ 明确表达空与非空"}]' />


## 预测复杂表达式：练习、自测与速记

<Exercise title='基础：预测 and/or 的返回值' task='打印 1 and 2 and 3、0 or 0.0 or &#39;x&#39;、0 and (1 // 0)，并解释为什么第三个不抛 ZeroDivisionError。' solution='print(&#39;a&#39;, 1 and 2 and 3)\nprint(&#39;b&#39;, 0 or 0.0 or &#39;x&#39;)\nprint(&#39;c&#39;, 0 and (1 // 0))' explain='and/or 返回决定结果的操作数；0 为假使 and 短路，右侧 1 // 0 根本没执行，因此不会抛除零异常，直接返回 0。' />

<Exercise title='进阶：修好 or 兜底并验证真值协议' task='写 get(cfg, key, default) 用 is None 判断，验证 0 不被替换；再定义只实现 __len__ 的类，打印空实例与非空实例的 bool。' solution='def get(cfg, key, default):\n    v = cfg.get(key)\n    return default if v is None else v\nclass Bag:\n    def __init__(self, items): self.items = items\n    def __len__(self): return len(self.items)\nprint(&#39;zero_kept&#39;, get({&#39;t&#39;: 0}, &#39;t&#39;, 30))\nprint(&#39;missing&#39;, get({}, &#39;t&#39;, 30))\nprint(&#39;empty&#39;, bool(Bag([])), &#39;nonempty&#39;, bool(Bag([1])))' explain='is None 只把「键不存在」当没配，0 这类合法假值原样保留；实现 __len__ 后 bool() 按长度判定，空袋为假、非空袋为真。' />

<Quiz no='011-1' q='0 or 30 与显式 is None 兜底的区别在于？' :options='["or 会把 0、空容器等合法假值也替换成默认值，is None 只处理未设置", "两者完全一样", "or 一定更快所以更好", "is None 会抛异常"]' answer="0" explain='or 按真值判定，遇到 0 或空容器就当成假并取默认值；只有 is None 能区分「没配」与「配了 0 这个合法值」。' />

<Quiz no='011-2' q='-7 // 2 与 -7 % 2 分别是？' :options='["-4 与 1，整除向下取整且余数与除数同号", "-3 与 -1，向零截断", "-4 与 -1", "-3 与 1"]' answer="0" explain='整除按 floor 向负无穷取整得 -4；余数由 a - (q*b) 反算并与除数同号得 1，恒等式 -4*2+1 == -7 成立。' />

<Quiz no='011-3' q='1 and 2 and 3 的结果是？' :options='["3，返回决定结果的最后一个操作数", "True", "1", "6"]' answer="0" explain='and 在没有假值时会一直求值到最后一个操作数并返回它本身，不做布尔转换；只有显式 bool() 才得到 True。' />

<Predict no='011-4' q='主示例里 print(&#39;or_value&#39;, 0 or 0.0 or &#39;default&#39;) 输出什么？' :options='["or_value default", "or_value True", "or_value 0"]' answer='0' output='or_value default' explain='or 从左到右返回第一个真值操作数；0 与 0.0 都是假值，于是返回字符串 default，而不是布尔 True。' />

<FillBlank no='011-5' tpl='___ 0 or 0.0 or &#39;default&#39;)' :answers='["print(&#39;or_value&#39;,"]' hint='回想本讲关于 算术与整除 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 算术、整除与比较链：结果的符号不是凭直觉 的落点。' />

<KnowledgeCard :points='["// 向下取整、-7 // 2 得 -4；% 与除数同号且满足 a == (a//b)*b + a%b，divmod 一次返回两者", "比较链 1 &lt; 2 &lt; 3 等价于 1 &lt; 2 and 2 &lt; 3，中间操作数只求值一次；幂运算 ** 右结合", "and/or 返回决定结果的操作数而非布尔值且短路右侧；0 and (1 // 0) 不抛异常", "用 or 兜底会替换 0、空容器等合法假值，应显式判断 is None", "海象 :=（3.8 起）在表达式内赋值并返回该值，需括号；真值测试查 __bool__ 再查 __len__", "and/or 无重载钩子，__and__ 是位与 &amp; 的入口；自定义容器不实现 __len__ 则恒为真"]' :pitfalls='["用 or 给可能为 0 或空容器的值兜底", "以为 and/or 返回布尔值，或把 __and__ 当成 and 的重载", "自定义容器不实现 __bool__ 或 __len__ 就放进 if", "用 or 给可能为 0 或空容器的值兜底，会把合法的假值悄悄替换掉，应显式判断 is None"]' summary='and / or 返回的不是布尔值，而是决定结果的那个操作数，这个特性让默认值的写法既简洁又暗藏陷阱' />

1. // 向下取整、-7 // 2 得 -4；% 与除数同号且满足 a == (a//b)*b + a%b，divmod 一次返回两者

2. 比较链 1 < 2 < 3 等价于 1 < 2 and 2 < 3，中间操作数只求值一次；幂运算 ** 右结合

3. and/or 返回决定结果的操作数而非布尔值且短路右侧；0 and (1 // 0) 不抛异常

[下一讲：分支：if / elif / else 与 match-case](/foundation/control-flow)
