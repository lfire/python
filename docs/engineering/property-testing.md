---
title: 第 077 讲 · 属性测试、基准测试与模糊测试
description: 用生成的输入发现手写用例想不到的边界
---

<StageHeader stage='L7 · 工程化' level='★★★★☆' time='35 分钟' goal='用生成的输入发现手写用例想不到的边界' prereq='第 076 讲 · Mock 与测试替身：时间、网络与随机' />

# 第 077 讲 · 属性测试、基准测试与模糊测试

替身把不稳定依赖稳住了，可手写用例总有想不到的组合。一个 URL 编解码函数上线后，只在昵称长得像转义序列时把换行弄错；空串、中文、真实换行这些用例全过，偏偏没人写那种「内容本身像指令」的输入，盲区是成片存在的。

我们换个问法往前走：先讲属性测试不问某个输入对不对、而问一类输入上性质是否成立，再看 hypothesis 策略怎样生成数据并收缩到最小反例，接着谈状态机测试，然后用 pytest-benchmark 给性能设回归阈值，末了补模糊测试与种子复现。带着纯函数、测试与参数化来；学完能把发现的反例固化成回归用例，给基准加上阈值。


## 手写用例覆盖了空串、中文、换行，偏偏漏了长得像转义序列的输入

一个 URL 编解码函数上线后，只在用户昵称里带字面量 NL 时把换行弄错。手写用例覆盖了空串、中文、真实换行，全都通过——偏偏没人写「内容本身就长得像转义序列」这种组合。另一处慢查询重构后无人察觉，因为压根没有基准回归阈值。手工用例的盲区是系统性的：编码、空值、极值、Unicode、超长串这些真实事故源永远写不全。

属性测试换个问法——不问「这个输入对不对」，而问「对所有这类输入，某条性质是否成立」，再用生成的输入把性质压垮并收缩到最小反例。本讲把 hypothesis 策略、收缩、状态机测试，以及基准测试与模糊测试的边界讲到能补上这类盲区。

<Callout type="warn" title='先看一个真实会出错的写法' text='只写正常输入的手工用例：编码、空值、极值、Unicode、超长串、字面量撞转义序列这些事故源永远写不全' />


## 从「例子」到「性质」：属性测试问的问题不一样

hypothesis 用 @`given(st.integers()`, `st.lists(st.text()`)) 声明输入空间，测试体写一条对所有输入都应成立的性质：不变量（排序后仍有序）、往返（`decode(encode(s)`) == s）、神谕（与一个可信参考实现比对）、变形（输入做等价变换后输出关系不变）、幂等（`f(f(x)`) == `f(x)`）。

策略可用 `st.integers(min_value, max_value)`、`st.text()`、`st.lists`、`st.one_of`、`st.builds`、@`st.composite` 组合，`settings(max_examples=100, derandomize=True, deadline=...)` 控制规模与时限，@`example(...)` 把显式边界钉进用例。

发现失败后 hypothesis 会沿随机选择序列做 delta-debugging 收缩，把反例压到最小并存进 .hypothesis/examples 数据库，下次自动重放，等于把事故固化成回归用例。

可验证：对一个把换行替换成 NL 的非单射编码，穷举长度≤3 的小字母表得到 85 个候选、9 个反例，收缩后最小反例是字面量 'NL'。

<Callout type="tip" title='核心心智模型' text='hypothesis 用 @given(st.integers(), st.lists(st.text())) 声明输入空间，测试体写一条对所有输入都应成立的性质：不变量（排序后仍有序）、往返（decode(encode(s)) == s）、神谕（与一个可信参考实现比对）、变形（输入做等价变换后输出' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段七 · 工程化与质量 |
| 前置 | 第 076 讲 · Mock 与测试替身：时间、网络与随机 |
| 难度 / 建议时长 | ★★★★☆ · 35 分钟 |
| 本讲新增 | hypothesis 策略、收缩到最小反例、状态机测试 |
| 一句话目标 | 用生成的输入发现手写用例想不到的边界 |
| 为下一讲铺垫 | 日志：logging、结构化日志与追踪关联 |


## strategy 怎么生成输入：hypothesis 常用构造

**属性测试常用构造（hypothesis）**

| 构造 | 作用 | 备注 |
| --- | --- | --- |
| @given(st.integers(), st.text()) | 声明输入策略 | 一条性质跑上百组输入 |
| st.integers / st.lists / st.one_of | 组合策略 | 用 min_value 等约束范围 |
| settings(max_examples=100, derandomize=True) | 规模与可复现 | deadline 控单例时限 |
| @example('NL') | 钉死显式反例 | 把事故固化成回归用例 |
| .hypothesis/examples | 反例数据库 | 下次自动重放 |
| RuleBasedStateMachine + @rule + Bundle | 状态机测试 | 操作序列一起收缩 |
| HealthCheck.too_slow / filter_too_much | 失效信号 | 应修策略而非一律关闭 |

<Term word='hypothesis 策略' text='hypothesis 用 @given(st.integers(), st.lists(st.text())) 声明输入空间，测试体写一条对所有输入都应成立的性质：不变量（排序后仍有序）、往返（decode(encode(s)) == s）、神谕（与一个可信参考实现比对）、变形（输入做等价变换后输出关系不变）、幂等（f' />

<Term word='收缩到最小反例' text='收缩的价值不只是「短」，而是把复杂的失败输入化简到能一眼看懂的本质：从 &#39;xNLy&#39;、&#39;NLNLNL&#39; 这类输入逐步删字符，只要删后仍触发失败就继续，最终停在 &#39;NL&#39;，正好暴露「编码不是单射」这个根因。状态机测试用 RuleBasedStateMachine + @initialize + @rule + Bundl' />


## 对照：手写用例与 @given 找到的反例

```python
import itertools

def encode(s):
    return s.replace(chr(10), 'NL')

def decode(s):
    return s.replace('NL', chr(10))

def prop(s):
    return decode(encode(s)) == s

alphabet = ['N', 'L', chr(10), 'a']
candidates = [''.join(p) for n in range(4) for p in itertools.product(alphabet, repeat=n)]
failing = [s for s in candidates if not prop(s)]
print('generated cases', len(candidates))
print('counterexamples', len(failing))

def shrink(s):
    best = s
    changed = True
    while changed:
        changed = False
        for i in range(len(best)):
            cand = best[:i] + best[i+1:]
            if cand and not prop(cand):
                best = cand
                changed = True
                break
    return best

minimal = {shrink(s) for s in failing}
print('minimal', sorted(m for m in minimal))
```

<OutputBox title='主示例运行结果' output='generated cases 85\ncounterexamples 9\nminimal [&#39;NL&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import itertools\n\ndef encode(s):\n    return s.replace(chr(10), &#39;NL&#39;)\n\ndef decode(s):\n    return s.replace(&#39;NL&#39;, chr(10))\n\ndef prop(s):\n    return decode(encode(s)) == s\n\nalphabet = [&#39;N&#39;, &#39;L&#39;, chr(10), &#39;a&#39;]\ncandidates = [&#39;&#39;.join(p) for n in range(4) for p in itertools.product(alphabet, repeat=n)]\nfailing = [s for s in candidates if not prop(s)]\nprint(&#39;generated cases&#39;, len(candidates))\nprint(&#39;counterexamples&#39;, len(failing))\n\ndef shrink(s):\n    best = s\n    changed = True\n    while changed:\n        changed = False\n        for i in range(len(best)):\n            cand = best[:i] + best[i+1:]\n            if cand and not prop(cand):\n                best = cand\n                changed = True\n                break\n    return best\n\nminimal = {shrink(s) for s in failing}\nprint(&#39;minimal&#39;, sorted(m for m in minimal))' :notes='["导入 itertools，用笛卡尔积穷举小输入空间", "定义编码：把换行替换成字面量 NL", "这个替换不是单射，是后续反例的根因", "定义解码：把 NL 还原成换行", "含字面量 NL 的原文会被误还原", "定义性质：编解码往返必须等于原串", "字母表含 N、L、真实换行与普通字符", "生成长度 0 到 3 的全部候选串，共 85 个", "挑出所有破坏往返性质的反例", "打印生成规模，证明覆盖远超手写用例", "打印反例数量", "定义收缩：逐步删字符逼近最小反例", "best 保存当前最短的失败输入", "changed 标记本轮是否还能继续收缩", "每轮重置标志", "逐个位置尝试删除一个字符", "构造删去第 i 位的候选", "候选非空且仍失败才接受", "接受更短的失败输入", "标记本轮有进展，继续下一轮", "找到一处成功收缩即重新开始", "返回不可再收缩的最小反例", "对所有反例收缩并去重成集合", "打印最小反例，暴露非单射根因", "属性测试问「对所有这类输入性质是否成立」：不变量、往返、神谕、变形、幂等", "hypothesis 用 @given + 策略生成输入，settings(max_examples, derandomize) 控规模与可复现"]' title='第 077 讲 · 属性测试、基准测试与模糊测试' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import timeit

def loop_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total

def builtin_sum(n):
    return sum(range(n))

t_loop = timeit.timeit(lambda: loop_sum(5000), number=200)
t_builtin = timeit.timeit(lambda: builtin_sum(5000), number=200)
print('builtin faster', t_builtin < t_loop)
print('both correct', loop_sum(5000) == builtin_sum(5000))
```

<OutputBox title='对照写法：先自己猜，再点开' output='builtin faster True\nboth correct True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import itertools\n\ndef encode(s):\n    return s.replace(chr(10), &#39;NL&#39;)\n\ndef decode(s):\n    return s.replace(&#39;NL&#39;, chr(10))\n\ndef prop(s):\n    return decode(encode(s)) == s\n\nalphabet = [&#39;N&#39;, &#39;L&#39;, chr(10), &#39;a&#39;]\ncandidates = [&#39;&#39;.join(p) for n in range(4) for p in itertools.product(alphabet, repeat=n)]\nfailing = [s for s in candidates if not prop(s)]\nprint(&#39;generated cases&#39;, len(candidates))\nprint(&#39;counterexamples&#39;, len(failing))\n\ndef shrink(s):\n    best = s\n    changed = True\n    while changed:\n        changed = False\n        for i in range(len(best)):\n            cand = best[:i] + best[i+1:]\n            if cand and not prop(cand):\n                best = cand\n                changed = True\n                break\n    return best\n\nminimal = {shrink(s) for s in failing}\nprint(&#39;minimal&#39;, sorted(m for m in minimal))", "note": "属性测试：从「例子」到「性质」"}, {"label": "对照 / 进阶", "code": "import timeit\n\ndef loop_sum(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n\ndef builtin_sum(n):\n    return sum(range(n))\n\nt_loop = timeit.timeit(lambda: loop_sum(5000), number=200)\nt_builtin = timeit.timeit(lambda: builtin_sum(5000), number=200)\nprint(&#39;builtin faster&#39;, t_builtin &lt; t_loop)\nprint(&#39;both correct&#39;, loop_sum(5000) == builtin_sum(5000))", "note": "收缩、状态机测试与可复现"}]' title='两种写法切换看' />


## 收缩到最小反例、状态机测试与种子可复现

收缩的价值不只是「短」，而是把复杂的失败输入化简到能一眼看懂的本质：从 'xNLy'、'NLNLNL' 这类输入逐步删字符，只要删后仍触发失败就继续，最终停在 'NL'，正好暴露「编码不是单射」这个根因。

状态机测试用 RuleBasedStateMachine + @initialize + @rule + Bundle 描述「对系统做一串操作后不变量仍成立」，例如内存字典模型与被测缓存对比：每步 @rule 随机挑一个操作执行并断言模型一致，hypothesis 连操作序列一起收缩，能抓到手写用例想不到的顺序组合。

可复现靠 `derandomize=True`、@`seed(...)`、`print_blob=True`（打印重放 blob）与提交 example 数据库；

`HealthCheck.too_slow` / filter_too_much / data_too_large 是策略写坏时的失效信号，不要一律关掉，而要修正策略写法本身；

找到的每个反例都应转成 @example 固定下来，让它长期守在回归套件里。

```python
import random, sys

def stream(seed, k=6):
    rng = random.Random(seed)
    return [rng.randrange(1000) for _ in range(k)]

print('seeded reproducible', stream(7) == stream(7))
print('seed 7 differs from 8', stream(7) != stream(8))
print('interpreter', sys.version_info[0], sys.version_info[1])
```

<OutputBox title='原理验证' output='seeded reproducible True\nseed 7 differs from 8 True\ninterpreter 3 13' />

<ConceptDiagram type='layers3' title='第 077 讲 · 属性测试：从「例子」到「性质」' labels='属性测试：从「例子」到「性质」|收缩、状态机测试与可复现|基准测试与模糊测试：别和属性测试混为一谈' caption='用生成的输入发现手写用例想不到的边界' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

```bash
python -m pytest -q --disable-warnings
```

把输入换成你自己的数据，观察结果是否仍符合 **hypothesis 策略** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## hypothesis 把一次运行建模成选择序列的底层

hypothesis 把一次测试运行建模为「从策略里抽取一串随机选择」：每个整数、字符都是选择序列上的一个节点，失败后 delta-debugging 逐段尝试删除/简化这些选择，只要删后仍失败就保留，直到得到最小选择序列，于是复杂输入被压成本质反例并将该序列哈希存进 .hypothesis/examples 供重放；

derandomize 固定熵源让整条序列确定。

往返性质 `decode(encode(s)`) == s 要求编码是单射，而把换行替换成字面量 NL 违反了这一点（含 'NL' 的原文解码后变成换行），所以收缩停在两字符 'NL'。

timeit 在计时期间 `gc.disable()`、执行 number 次并取多轮最小以降低调度噪声；`sum(range(n)`) 走 C 层循环，指令数远少于等价的 Python for 累加，方向稳定。

覆盖率引导的 fuzzer 则给基本块插桩，只保留触发新分支的输入，与「结构化输入 + 语义收缩」的属性测试是互补的两套机制。


## 基准测试、模糊测试与属性测试的边界

基准测量的是「多快」，属性/模糊测的是「对不对」。

pytest-benchmark 提供 benchmark fixture：`benchmark(fn, *args)` 自动校准轮数（--benchmark-min-rounds）、给出 min/median/mean/ops 并写 JSON，--benchmark-compare 对比历史、--benchmark-autosave 存档，CI 里设回归阈值——某次提交让耗时翻倍就失败。

标准库 `timeit.timeit(stmt, number=...)` 计时期间会关掉 GC、跑 number 次取代表值，`timeit.repeat` 多轮取最小以压噪声；

内置 `sum(range(n)`) 是 C 循环，稳定快于等价的 Python for 累加（可验证方向一致）。模糊测试（AFL/libFuzzer，Python 侧 atheris）生成无结构、偏边界的随机字节，靠插桩记录覆盖了哪些分支来保留「能走到新路径」的输入，目标是崩溃与越界，不做语义收缩；

属性测试输入结构化、带收缩、验证性质。三者互补：纯函数与解析器加属性测试，热点加基准阈值，外部输入解析加模糊测试。

**三类测试的边界与选型**

| 类型 | 问的问题 | 典型工具 / 产物 |
| --- | --- | --- |
| 属性测试 | 对所有这类输入性质是否成立 | hypothesis，最小反例 |
| 基准测试 | 这段代码多快、是否回归 | pytest-benchmark / timeit，回归阈值 |
| 模糊测试 | 随机字节会不会崩/越界 | AFL / libFuzzer / atheris，覆盖率引导 |
| 手写单测 | 这个具体输入对不对 | pytest 用例 |
| 状态机测试 | 一串操作后不变量是否保持 | hypothesis RuleBasedStateMachine |

**收缩与基准的关键数值 / 信号**

| 项 | 值 / 信号 | 含义 |
| --- | --- | --- |
| 本讲穷举候选数 | 85（长度 0-3、4 字符字母表） | 远超手写用例覆盖 |
| 往返反例数 | 9 | 编码非单射导致 |
| 最小反例 | 'NL' | 删到不能再删的本质输入 |
| timeit.number | 示例 200 | 计时期间关 GC 跑多轮 |
| builtin faster | True（方向稳定） | sum 是 C 循环快于 Python for |
| seeded reproducible | True | 同 seed 同序列，反例可复现 |


## 把属性测试发现的最小反例固化为回归用例

属性测试真正的工程价值在收尾：生成的输入发现失败后，要把收缩得到的最小反例写回测试套件，让这次事故永久守门。

压缩连续空格的函数若只做一轮替换就不满足幂等性质 `compact(compact(s)`) == `compact(s)`，长空白串会触发失败；

对小字母表穷举候选、逐个收缩、去重成最小集合，再把它们序列化成回归清单随代码提交。下面片段用标准库走完「生成 → 找反例 → 收缩 → 固化」整条链路，重点看最小反例如何暴露根因，而不是记住某个具体输入。

```python
import itertools, json

def compact(s):
    return s.replace('  ', ' ')

def prop(s):
    r = compact(s)
    return compact(r) == r

alphabet = [' ', 'a']
cases = [''.join(p) for n in range(6) for p in itertools.product(alphabet, repeat=n)]

def shrink(s):
    best = s
    changed = True
    while changed:
        changed = False
        for i in range(len(best)):
            cand = best[:i] + best[i + 1:]
            if not prop(cand):
                best = cand
                changed = True
                break
    return best

failing = [s for s in cases if not prop(s)]
minimal = sorted({shrink(s) for s in failing})
print('generated', len(cases), 'failing', len(failing))
print('minimal', [repr(m) for m in minimal[:3]])
print('pinned regression', json.dumps([repr(m) for m in minimal[:3]]))
```

<Callout type="idea" title='落地提示' text='给纯函数与解析器加属性测试，把发现的反例固化成回归用例；基准测试设回归阈值' />

<CheckList id='P077b' title='上线前自检' :items='["能复现并解释「只写正常输入的手工用例」", "能复现并解释「找到反例却不固化、或一律关掉 HealthCheck」", "能复现并解释「把基准当一次性数字、没有回归阈值」", "能用一条命令验证 hypothesis 策略", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只写正常输入的手工用例 | 编码、空值、极值、Unicode、超长串、字面量撞转义序列这些事故源永远写不全 | 给纯函数与解析器加往返/幂等/神谕性质，用 @given 生成输入，反例固化成 @example |
| 找到反例却不固化、或一律关掉 HealthCheck | 下次运行换随机序列可能不再复现，too_slow/filter_too_much 被硬关会掩盖策略写坏 | 把最小反例写进 @example 并提交 .hypothesis/examples；针对告警修策略而不是全局 suppress_health_check |
| 把基准当一次性数字、没有回归阈值 | 重构让耗时翻倍也不会让 CI 变红，性能退化静默累积 | pytest-benchmark 设 --benchmark-compare 与回归阈值，timeit 多轮取最小，热点提交前后都测 |

<Callout type="warn" title='本讲最容易踩的坑' text='只写正常输入的手工用例：编码、空值、极值、Unicode、超长串、字面量撞转义序列这些事故源永远写不全' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只写正常输入的手工用例", "body": "编码、空值、极值、Unicode、超长串、字面量撞转义序列这些事故源永远写不全", "tip": "给纯函数与解析器加往返/幂等/神谕性质，用 @given 生成输入，反例固化成 @example"}, {"title": "第 2 步：找到反例却不固化、或一律关掉 HealthC", "body": "下次运行换随机序列可能不再复现，too_slow/filter_too_much 被硬关会掩盖策略写坏", "tip": "把最小反例写进 @example 并提交 .hypothesis/examples；针对告警修策略而不是全局 suppress_health_check"}, {"title": "第 3 步：把基准当一次性数字、没有回归阈值", "body": "重构让耗时翻倍也不会让 CI 变红，性能退化静默累积", "tip": "pytest-benchmark 设 --benchmark-compare 与回归阈值，timeit 多轮取最小，热点提交前后都测"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：写一条往返性质并发现反例' task='定义把换行替换成 NL 的 encode/decode，验证 &#39;a&#39; 加换行加 &#39;b&#39; 往返成立、而字面量 &#39;NL&#39; 往返失败。' solution='def encode(s):\n    return s.replace(chr(10), &#39;NL&#39;)\ndef decode(s):\n    return s.replace(&#39;NL&#39;, chr(10))\nprint(&#39;roundtrip ok&#39;, decode(encode(&#39;a&#39; + chr(10) + &#39;b&#39;)) == &#39;a&#39; + chr(10) + &#39;b&#39;)\nprint(&#39;collision&#39;, decode(encode(&#39;NL&#39;)) == &#39;NL&#39;)' explain='往返性质要求编码单射；字面量 NL 与真实换行被映射到同一表示，解码时无法区分，正是属性测试要抓的碰撞。' />

<Exercise title='进阶：用 timeit 对比两种实现' task='用 timeit.timeit 分别测 sum(range(1000)) 与列表推导求和，确认结果相等且两种写法都被计时。' solution='import timeit\na = timeit.timeit(lambda: sum(range(1000)), number=100)\nb = timeit.timeit(lambda: sum([i for i in range(1000)]), number=100)\nprint(&#39;both equal&#39;, sum(range(1000)) == sum([i for i in range(1000)]))\nprint(&#39;timed&#39;, a &gt; 0 and b &gt; 0)' explain='timeit 关 GC 跑 number 次取代表值；正确性用结果相等守住，性能差异交给基准工具与回归阈值判断，别把手写计时当结论。' />

<Quiz no='077-1' q='属性测试与手写用例的核心区别是？' :options='["对所有这类输入验证某条性质成立，并生成输入 + 收缩最小反例", "逐个检查预设的具体输入", "只测运行速度", "专门测网络超时"]' answer="0" explain='属性测试把「这个输入对不对」换成「性质是否对所有输入成立」，靠策略生成覆盖、靠收缩定位根因，能抓到手写用例想不到的组合。' />

<Quiz no='077-2' q='关于 hypothesis 的收缩，准确的是？' :options='["沿随机选择序列 delta-debugging 删到最小失败输入并存库重放", "把输入按长度排序取第一个", "直接丢弃失败输入", "只保留最长的失败输入"]' answer="0" explain='收缩逐段删除/简化选择序列，只要删后仍失败就保留，得到最小反例并写进 .hypothesis/examples；配 @example 可永久固化为回归用例。' />

<Quiz no='077-3' q='pytest-benchmark 相比一次性 timeit 数字的关键增益是？' :options='["自动校准轮数、存历史 JSON、--benchmark-compare 对比并设回归阈值", "让代码跑得更快", "自动生成属性测试", "替代单元测试"]' answer="0" explain='benchmark fixture 校准轮数、给 min/median/ops、保存 JSON 供 compare；CI 设回归阈值后耗时翻倍会失败，避免性能退化静默累积。' />

<Predict no='077-P' q='把换行替换成 NL 的编码，对候选串收缩后最小反例最可能是？' :options='["[&#39;NL&#39;]", "[&#39;xNLy&#39;]", "[]"]' answer='0' output='[&#39;NL&#39;]' explain='删字符只要仍触发往返失败就继续，&#39;xNLy&#39;、&#39;NLNLNL&#39; 都会被压到两字符 &#39;NL&#39;——它正是「编码非单射」的最小证据，再删任一字符性质就恢复成立。' />

<FillBlank no='077-F' tpl='___ itertools' :answers='["import"]' hint='回想本讲关于 hypothesis 策略 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 属性测试：从「例子」到「性质」 的落点。' />

<KnowledgeCard :points='["属性测试问「对所有这类输入性质是否成立」：不变量、往返、神谕、变形、幂等", "hypothesis 用 @given + 策略生成输入，settings(max_examples, derandomize) 控规模与可复现", "失败沿随机选择序列做 delta-debugging 收缩到最小反例，存 .hypothesis/examples 并用 @example 固化", "RuleBasedStateMachine + @rule + Bundle 测状态不变量；HealthCheck 告警要修策略不要硬关", "pytest-benchmark 自动校准、存 JSON、--benchmark-compare 设回归阈值；timeit 关 GC 多轮取最小", "模糊测试（atheris/AFL）覆盖率引导、无结构输入、不收缩；与属性测试的输入与语义互补"]' :pitfalls='["只写正常输入的手工用例", "找到反例却不固化、或一律关掉 HealthCheck", "把基准当一次性数字、没有回归阈值", "只测正常输入，等于没测编码、空值、极值、Unicode 与超长字符串这些真实事故来源"]' summary='属性测试不问「这个输入对不对」，而问「对所有这类输入，性质是否成立」，因此能抓到手工用例永远不会写的组合' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 属性测试问「对所有这类输入性质是否成立」：不变量、往返、神谕、变形、幂等 | 建立直觉 |
| hypothesis 用 @given + 策略生成输入，settings(max_examples, derandomize) 控规模与可复现 | 跑通示例 |
| 失败沿随机选择序列做 delta-debugging 收缩到最小反例，存 .hypothesis/examples 并用 @example 固化 | 深入边界 |
| RuleBasedStateMachine + @rule + Bundle 测状态不变量；HealthCheck 告警要修策略不要硬关 | 工程落地 |
| pytest-benchmark 自动校准、存 JSON、--benchmark-compare 设回归阈值；timeit 关 GC 多轮取最小 | 随堂检测 |
| 模糊测试（atheris/AFL）覆盖率引导、无结构输入、不收缩；与属性测试的输入与语义互补 | 复盘 |

1. 属性测试问「对所有这类输入性质是否成立」：不变量、往返、神谕、变形、幂等

2. hypothesis 用 @given + 策略生成输入，settings(max_examples, derandomize) 控规模与可复现

3. 失败沿随机选择序列做 delta-debugging 收缩到最小反例，存 .hypothesis/examples 并用 @example 固化

[下一讲：日志：logging、结构化日志与追踪关联](/engineering/logging)
