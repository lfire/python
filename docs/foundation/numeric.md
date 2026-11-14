---
title: 第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool
description: 根据场景选对数值类型，避开精度陷阱
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='30 分钟' goal='根据场景选对数值类型，避开精度陷阱' prereq='第 007 讲 · 变量是名字绑定：赋值、引用与命名规范' />

# 第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool

名字与赋值都清楚了，总算能踏实算点东西。可『数字』并非铁板一块：整数、小数、金额或比率各有脾气与场合。这一讲帮你把这套数值体系按场景理清。记账的人多半见过：几笔一毛两毛累加，结果和手算差一点点。这不是写错，是二进制表示十进制小数的必然。我们先看 int 如何不溢出、付了什么代价，顺带交代 bool 是 int 子类；再拆开 float 与 `IEEE 754`，弄清浮点误差从哪来、比较为何用 `math.isclose`；最后请出 Decimal 与 Fraction，把精度交还业务口径。会用变量与基本运算就够；学完面对金额与统计你能选对类型。


## 金额累加对不上账：0.1 + 0.2 为什么不是 0.3

财务系统里有人把订单金额累加写成 `total += 0.1`，跑完一万条后对账差了几分钱；

排查时用 `print(total == expected)` 得到 False，于是改成 `round(total, 2)`，可换个批次又对不上。

另一个脚本要生成大额订单号，直接 `2 ** 100` 得到 31 位整数却担心溢出，加了一堆没必要的取模；

还有人用 float 存利率，把 `0.1 + 0.2 == 0.3` 写成断言，测试直接挂掉。

朴素解法是「用 round 抹平误差」或「拿 == 判断两个计算结果相等」，两者都把表示法的问题当成计算的问题：float 用二进制近似十进制，0.1 根本无法被有限位二进制精确表示，误差会随累加放大。Python 的 int 反而是任意精度、不会溢出，代价是位数越多运算越慢。

本讲把四类数值的表示、误差来源、比较与量化规则讲清，并给出金额用 Decimal、科学计算用明确 dtype 的选型依据。


## int 任意精度与 bool：不会溢出的代价

CPython 的 int 是变长对象：PyLongObject 用一个 digit 数组（64 位平台默认每 digit 存 30 位）保存绝对值，`ob_size` 带符号记录长度，因此数值没有固定上限，`2 ** 100` 得到 31 位十进制数完全合法，只有内存是边界。

代价是位数越多，加减乘除要遍历的 digit 越多，大整数运算明显慢于机器字长的 C int，`sys.getsizeof(0)` 与 `sys.getsizeof(2 ** 100)` 的差就是变长存储的证据。

3.11 起还加了安全限制：int 与 str 互转默认最多 4300 位十进制，超过抛 ValueError，可用 `sys.set_int_max_str_digits` 调整或置 0 关闭，目的是防止超长数字字符串把 CPU 拖死。

bool 是 int 的子类，True 与 False 就是 1 与 0 的单例，因此 `isinstance(True, int)` 为真、`True + True` 得 2；

但 `type(True) is bool`，做类型判断时别把布尔当普通整数收进金额统计。

位运算直接作用在整型的二进制补码语义上：`1 << 10` 得 1024，`0b1100 & 0b1010` 得 8；

复数用 `3 + 4j` 字面量，`abs(3 + 4j)` 返回 5.0，实部虚部都是 float。

```python
from decimal import Decimal
from fractions import Fraction
import math

print('float_sum', 0.1 + 0.2)
print('equal', 0.1 + 0.2 == 0.3)
print('isclose', math.isclose(0.1 + 0.2, 0.3))
print('decimal', Decimal('0.1') + Decimal('0.2'))
print('decimal_eq', Decimal('0.1') + Decimal('0.2') == Decimal('0.3'))
print('fraction', Fraction(1, 3) + Fraction(1, 6))
```

<OutputBox title='主示例运行结果' output='float_sum 0.30000000000000004\nequal False\nisclose True\ndecimal 0.3\ndecimal_eq True\nfraction 1/2' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from decimal import Decimal\nfrom fractions import Fraction\nimport math\n\nprint(&#39;float_sum&#39;, 0.1 + 0.2)\nprint(&#39;equal&#39;, 0.1 + 0.2 == 0.3)\nprint(&#39;isclose&#39;, math.isclose(0.1 + 0.2, 0.3))\nprint(&#39;decimal&#39;, Decimal(&#39;0.1&#39;) + Decimal(&#39;0.2&#39;))\nprint(&#39;decimal_eq&#39;, Decimal(&#39;0.1&#39;) + Decimal(&#39;0.2&#39;) == Decimal(&#39;0.3&#39;))\nprint(&#39;fraction&#39;, Fraction(1, 3) + Fraction(1, 6))' :notes='["导入 Decimal：十进制表示，金额场景用它避免二进制误差", "导入 Fraction：用整数分子分母做精确有理数运算", "导入 math 以使用浮点近似比较 isclose", "空行，只用于分隔逻辑块，不影响执行结果。", "0.1 与 0.2 的二进制近似相加得 0.30000000000000004", "用 == 判断两个浮点计算结果相等，结果为 False", "math.isclose 按相对容差判定，二者视为足够接近", "字符串构造的 Decimal 精确相加得 0.3", "Decimal 的 == 比较值，精确相等故为 True", "Fraction 精确通分，1/3 加 1/6 打印成 1/2"]' title='第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## float 与 IEEE 754：二进制近似十进制

float 对应 C 的 double，遵循 `IEEE 754` 二进制 64 位：1 位符号、11 位指数、52 位尾数，约 15 到 17 位有效十进制数字。

十进制的 0.1 转成二进制是无限循环小数，只能存成最接近的近似值，`struct.pack('>d', 0.1).hex()` 得到 3fb999999999999a 就是证据；

`0.1 + 0.2` 因此等于 0.30000000000000004，与 0.3 不相等。这不是 bug，是二进制浮点表示十进制小数的必然。

比较计算结果一律用 `math.isclose(a, b)`，它默认 `rel_tol=1e-9`、`abs_tol=0.0`，判定取相对容差与绝对容差中较大者：`rel_tol` 乘 `max(abs(a), abs(b))` 与 `abs_tol` 谁大用谁，只要 `abs(a - b)` 不超过这个上限就算接近。

把相差 `1e-10` 的两个数交给 `math.isclose`，默认容差下判为真；把 `rel_tol` 收紧后比较 1.0 与 1.0001 则为假。`sys.float_info` 给出 epsilon（约 2.22e-16）、`radix=2`、max 与 min 等机器常量。

还要注意 `float('nan')` 与自身用 == 比较恒为 False，判断 NaN 必须用 `math.isnan`；`float('inf')` 参与运算会产生无穷或 nan。用 == 判断两个浮点计算结果相等是财务系统最典型的线上事故，因为它把表示误差当成了逻辑差异。

还要留意一个容易混淆的版本差异：3.12 起 `sum()` 对浮点输入改用补偿求和，`sum([0.1] * 10)` 因此恰好得到 1.0，而手写 += 循环累加十次仍是 0.9999999999999999；

因此「浮点一定不精确」与「sum 一定不精确」都不是准确结论，要看有没有补偿、误差是否被这次舍入吃掉。


### 浮点误差怎么用 math.isclose 判定

够不够用，看两个数离 0 多远。

isclose 让 rel_tol 与 abs_tol 取较大者，近 0 时 rel_tol 几乎归零：`math.isclose(0.0, 1e-10)` 默认 False，传 `abs_tol=1e-9` 才认。

量级大时该调 rel_tol，别设成 0 否则只剩绝对容差。这个 API 3.5 由 PEP 485 加入，复数走 `cmath.isclose`；NaN 与任何值比较都 False，先用 `math.isnan` 拦。下表列几组取值与判定结果，按数量级入座。

**math.isclose 参数与判定**

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| rel_tol | 1e-9 | 相对容差，乘以两数中较大的绝对值 |
| abs_tol | 0.0 | 绝对容差，处理接近零的比较 |
| 判定式 | 无 | abs(a-b) <= max(rel_tol*max(\|a\|,\|b\|), abs_tol) |


## Decimal、Fraction 与量化：把精度交还给业务规则

`decimal.Decimal` 用十进制表示，构造时必须传字符串：用 `Decimal('0.1')` 与 `Decimal('0.2')` 相加，结果精确等于 `Decimal('0.3')`，而 `Decimal(0.1)` 会把 float 的近似值一并带进来，得到一长串尾数。

Decimal 的运算受 context 控制：`decimal.getcontext().prec` 默认 28 位有效数字，rounding 默认 `ROUND_HALF_EVEN`（银行家舍入），可用 `localcontext()` 临时改；

金额要显式 `quantize(Decimal('0.01'))` 把量化规则写进领域层，而不是最后随手 round。

`Fraction(1, 3)` 与 `Fraction(1, 6)` 相加得到 1/2，它用分子分母整数做精确有理数运算，适合比例与概率，但分母会随运算膨胀、比 float 慢得多。选型很清晰：金融与计量用 Decimal 并固定量化规则，避免任何二进制误差；需要精确分数用 Fraction；

科学计算与大规模数组用明确 dtype 的 NumPy，用空间换速度并接受浮点误差；一般计数用 int。不要用 float 累加金额、不要用 == 比较浮点计算结果、不要把 Decimal 与 float 混在一个表达式里（会抛 TypeError）。

```python
big = 2 ** 100
print('big_digits', len(str(big)))
print('no_overflow', big * big > big)
print('bool_sub', isinstance(True, int), True + True)
print('shift', 1 << 10)
print('bitand', 0b1100 & 0b1010)
print('complex', 3 + 4j, abs(3 + 4j))
```

<OutputBox title='对照写法：先自己猜，再点开' output='big_digits 31\nno_overflow True\nbool_sub True 2\nshift 1024\nbitand 8\ncomplex (3+4j) 5.0' guess="true" />


### Decimal(0.1) 与 Decimal('0.1') 的差别

差一个引号，差在入口：字符串走十进制解析，float 带着二进制近似值。

`Decimal(0.1)` 打印是一长串尾数，与 `from_float(0.1)` 等价。

`as_tuple()` 里，`Decimal('0.1')` 得 (0, (1,), -1)，从 float 构造的拖一长串数字。`Decimal(x)` == `Decimal('0.1')` 为假就是踩了 float 入口；要精确值用 `Decimal(1)`/`Decimal(10)`，prec 只管运算。

术语卡把「字符串或整数构造」与「float 构造」分栏。

<Term word='int 的任意精度实现' text='CPython 的 int 是变长对象：PyLongObject 用一个 digit 数组（64 位平台默认每 digit 存 30 位）保存绝对值，`ob_size` 带符号记录长度，因此数值没有固定上限，`2 ** 100` 得到 31 位十进制数完全合法，只有内存是边界。代价是位数越多，加减乘除要遍历的 digi…' />

<Term word='float 与 IEEE 754' text='float 对应 C 的 double，遵循 `IEEE 754` 二进制 64 位：1 位符号、11 位指数、52 位尾数，约 15 到 17 位有效十进制数字。十进制的 0.1 转成二进制是无限循环小数，只能存成最接近的近似值，`struct.pack(&#39;&gt;d&#39;, 0.1).hex()` 得到 3fb9999999…' />


## 四类数值类型怎么选：维度对照

**数值类型对照**

| 类型 | 表示 | 典型陷阱 | 适用场景 |
| --- | --- | --- | --- |
| int | 变长 digit 数组，任意精度 | 位数越多越慢；3.11 起 str 互转默认限 4300 位 | 计数、ID、位运算 |
| float | IEEE 754 二进制 64 位 | 0.1+0.2 不等于 0.3；nan 与自身不等 | 科学计算、测量值 |
| Decimal | 十进制加 context 精度 | 必须用字符串构造，混 float 抛 TypeError | 金额、计量 |
| Fraction | 整数分子分母 | 分母膨胀、运算慢 | 精确比例 |
| bool | int 子类，True/False 单例 | isinstance(True, int) 为真 | 逻辑判断 |
| complex | 实部虚部均为 float | abs 返回 float | 信号、复数运算 |


### 版本与机器常量：float_info 里能读到什么

把机器决定和版本决定分开，才不会把常量当语言保证。

`sys.float_info` 里 `dig=15`、`mant_dig=53`、epsilon、radix、max 俱全，`struct.calcsize('d')` 恒为 8。

版本另放：3.11 的 set_int_max_str_digits、3.12 起 sum 用补偿求和、3.13 可查 _is_gil_enabled；

`platform.python_implementation()` 在 PyPy 下这些值未必相同。

下表按机器、版本、实现三栏归位。

**版本与机器常量**

| 项 | 值或行为 | 来源 |
| --- | --- | --- |
| sys.float_info.epsilon | 约 2.22e-16 | IEEE 754 双精度 |
| sys.float_info.radix | 2 | 二进制浮点 |
| sys.get_int_max_str_digits() | 4300 | 3.11 起 int/str 互转上限 |
| decimal.getcontext().prec | 28 | Decimal 默认有效位 |
| decimal 默认 rounding | ROUND_HALF_EVEN | 银行家舍入 |
| sum() 对 float | 3.12 起补偿求和 | sum([0.1]*10) 得 1.0，手写循环仍 0.9999999999999999 |


## 底层：为什么 int 不溢出而 float 会丢精度

CPython 的 PyLongObject 用 `ob_size` 带符号记录 digit 数组长度，每 digit 在 64 位平台存 30 位，加减法逐 digit 进位、乘法走 Karatsuba 或更快的算法，因此整数不溢出但时间复杂度随位数增长。

PyFloatObject 直接包一个 C double，遵循 `IEEE 754`：符号 1 位、指数 11 位、尾数 52 位，规格化数隐含一个前导 1，故 0.1 这种分母含 5 的十进制小数无法用有限二进制表示，只能取最近可表示值，`struct.pack` 的十六进制字节把它暴露出来。

Decimal 则用十进制的系数加指数，配合一个线程局部的 Context 保存 prec、rounding、Emin 与 Emax，所有运算按十进制规则舍入，因此能与人工账本一致。`math.isclose` 把误差判定写成相对容差与绝对容差取较大者，避免接近零时相对容差失效。

理解这几种表示的数据结构，就能推断「为什么 int 不溢出」「为什么金额不能用 float」「为什么 Decimal 要用字符串构造」，而不用死记结论。

<ConceptDiagram type='hub4' title='第 008 讲 · int 任意精度与 bool：不会溢出的代价' labels='int 任意精度与 bool：不会溢出的代价|float 与 IEEE 754：0.1 +…|Decimal、Fraction 与量化：把…|复数与位运算' caption='根据场景选对数值类型，避开精度陷阱' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 结算服务：把量化规则写进领域层

一个结算服务要把一批交易按分位汇总、计算手续费并输出两位小数，早期实现全程 float，月末对账总差几分钱。下面这段给出工程写法：所有金额用字符串构造的 Decimal，累加后用 `quantize` 配合 `ROUND_HALF_UP` 把量化规则固定在领域层，手续费按比例 Decimal 计算，最后输出可核对的字符串；

同时用 float 版本在同一批数据上的结果说明为什么不能靠 round 兜底。真实系统还会把 context 的 prec 与 rounding 写进配置、对每笔交易留原始字符串，避免二次解析引入误差。重点是量化只做一次、且发生在明确的业务边界，而不是在打印前随手四舍五入。

```python
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math

CENT = Decimal('0.01')

def money(s):
    return Decimal(s)

def settle(rows, rate):
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        total = Decimal('0')
        for s in rows:
            total += money(s)
        fee = (total * Decimal(rate)).quantize(CENT)
        return (total + fee).quantize(CENT)

rows = ['0.10'] * 10
gross = settle(rows, '0.006')
float_sum = 0.0
for s in rows:
    float_sum += float(s)
print('decimal_total', gross)
print('float_exact', float_sum == 1.0)
print('float_isclose', math.isclose(float_sum, 1.0))
print('two_places', str(gross))
```

<Callout type="idea" title='落地提示' text='金融与计量用 Decimal 并把量化规则写进领域层；科学计算用 NumPy 的 dtype 明确精度与内存' />


## 金额与混算的错因速查

混算往往直接不让算：`Decimal('0.1')` + 0.2 抛 TypeError，报 Decimal 与 float 不能相加，表达式得先统一类型。静默那类更麻烦：True 被当 1 计入金额，bool 是 int 子类不报错，用 `type(x)` is bool 挡一道；

`getcontext().prec` 默认 28 位，连乘后截断，金额该 `quantize(Decimal('0.01'))` 落到分位；

`round()` 返回 float 救不了账目。下表按现象、根因、写法列出，配排查顺序。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 float 累加金额、用 == 判断两个计算结果相等 | 0.1 等十进制小数在二进制里是近似值，误差随累加放大，== 把表示误差当成逻辑差异 | 金额用 Decimal('0.10') 累加并 quantize 到分位；浮点比较用 math.isclose |
| 用 Decimal(0.1) 构造十进制数 | 传入 float 会把 float 已有的二进制近似值原样带进 Decimal，得到一长串尾数 | 一律用字符串 Decimal('0.1') 构造，或从 int 构造 |
| 把 True 当普通整数收进金额统计，或把 Decimal 与 float 混算 | bool 是 int 子类会悄悄计入求和；Decimal 与 float 做算术会抛 TypeError | 统计前用 type(x) is bool 排除；表达式里先统一成 Decimal，不混用 float |

<Callout type="warn" title='本讲最容易踩的坑' text='用 float 累加金额、用 == 判断两个计算结果相等：0.1 等十进制小数在二进制里是近似值，误差随累加放大，== 把表示误差当成逻辑差异' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 float 累加金额、用 == 判断两个…", "body": "0.1 等十进制小数在二进制里是近似值，误差随累加放大，== 把表示误差当成逻辑差异", "tip": "金额用 Decimal(&#39;0.10&#39;) 累加并 quantize 到分位；浮点比较用 math.isclose"}, {"title": "第 2 步：用 Decimal(0.1) 构造十进制数", "body": "传入 float 会把 float 已有的二进制近似值原样带进 Decimal，得到一长串尾数", "tip": "一律用字符串 Decimal(&#39;0.1&#39;) 构造，或从 int 构造"}, {"title": "第 3 步：把 True 当普通整数收进金额统计，或把…", "body": "bool 是 int 子类会悄悄计入求和；Decimal 与 float 做算术会抛 TypeError", "tip": "统计前用 type(x) is bool 排除；表达式里先统一成 Decimal，不混用 float"}]' />


## 按场景选数值类型：练习、自测与速记

<Exercise title='基础：用 Decimal 修好金额累加' task='把 0.1 累加十次，分别用 float 与 Decimal(&#39;0.1&#39;) 打印结果，并打印 float 版是否等于 1.0、Decimal 版是否等于 Decimal(&#39;1.0&#39;)。' solution='from decimal import Decimal\nf = 0.0\nd = Decimal(&#39;0&#39;)\nfor _ in range(10):\n    f += 0.1\n    d += Decimal(&#39;0.1&#39;)\nprint(&#39;float&#39;, f, f == 1.0)\nprint(&#39;decimal&#39;, d, d == Decimal(&#39;1.0&#39;))' explain='float 累加十次 0.1 得到 0.9999999999999999，与 1.0 不相等；Decimal 按十进制精确累加得到 1.0。金额不可靠 float 累加。' />

<Exercise title='进阶：给 isclose 选对容差' task='用 math.isclose 分别比较 1e9 与 1e9+1、1.0 与 1.0001，打印默认 rel_tol 下的结果，再对第二组收紧 rel_tol 并用 abs_tol 比较接近零的两个值。' solution='import math\nprint(&#39;large&#39;, math.isclose(1e9, 1e9 + 1))\nprint(&#39;small&#39;, math.isclose(1.0, 1.0001))\nprint(&#39;tight&#39;, math.isclose(1.0, 1.0001, rel_tol=1e-9))\nprint(&#39;with_abs&#39;, math.isclose(0.0, 1e-12, abs_tol=1e-9))' explain='相对容差随量级缩放：差 1 对 1e9 恰好落在 1e-9 边界内为真；差 1e-4 对 1.0 远超默认 rel_tol 为假；接近零时相对容差失效，须靠 abs_tol。' />

<Quiz no='008-1' q='0.1 + 0.2 不等于 0.3 的根本原因是？' :options='["二进制浮点无法精确表示十分之一，二者是不同近似值", "Python 的加法有 bug", "float 精度只有 6 位", "0.3 被四舍五入过"]' answer="0" explain='0.1 与 0.2 在 IEEE 754 双精度里都是无限循环二进制的截断近似，相加后最近可表示值与 0.3 的近似值不同，属于表示法必然结果。' />

<Quiz no='008-2' q='比较两个浮点计算结果是否相等，正确做法是？' :options='["math.isclose(a, b)，必要时配 rel_tol 与 abs_tol", "用 == 前先 round 两位", "转成 str 比较", "用 is 比较"]' answer="0" explain='math.isclose 用相对与绝对容差的较大者判定，能容纳表示误差；round 只是换一种截断，== 与 is 都不比较近似程度。' />

<Quiz no='008-3' q='构造十进制金额，哪种写法正确？' :options='["Decimal(&#39;0.1&#39;)，用字符串避免带入 float 近似", "Decimal(0.1)", "float(&#39;0.1&#39;)", "Fraction(0.1)"]' answer="0" explain='Decimal(0.1) 会把 float 已有的二进制近似原样带进来；Decimal 只接受字符串或整数才是精确十进制值。' />

<Predict no='008-4' q='主示例里 print(&#39;float_sum&#39;, 0.1 + 0.2) 输出什么？' :options='["0.30000000000000004", "0.3", "0.3000000000000000"]' answer='0' output='0.30000000000000004' explain='0.1 与 0.2 在 IEEE 754 双精度里都只能存成近似值，相加后最近可表示值是 0.30000000000000004，与 0.3 对应的近似值不同。' />

<FillBlank no='008-5' tpl='from decimal  ___ Decimal' :answers='["import"]' hint='回想本讲关于 int 的任意精度实现 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 int 任意精度与 bool：不会溢出的代价 的落点。' />

<KnowledgeCard :points='["int 是变长 digit 数组、不溢出，位数越多越慢；3.11 起 int/str 互转默认限 4300 位", "float 是 IEEE 754 双精度（符号 1 位、指数 11 位、尾数 52 位），用 math.isclose 比较", "math.isclose 默认 rel_tol=1e-9、abs_tol=0.0；接近零时靠 abs_tol 兜底", "Decimal 用字符串构造加 context（prec=28、ROUND_HALF_EVEN）；金额显式 quantize 到分位", "Fraction 做精确有理数但分母膨胀；Decimal 与 float 混算会抛 TypeError", "bool 是 int 子类；金额用 Decimal、科学计算用明确 dtype 的 NumPy"]' :pitfalls='["用 float 累加金额、用 == 判断两个计算结果相等", "用 Decimal(0.1) 构造十进制数", "把 True 当普通整数收进金额统计，或把 Decimal 与 float 混算", "金额用 float 累加、或用 == 判断两个计算结果相等，是财务系统最典型的线上事故"]' summary='Python 的 int 不会溢出，代价是位数越多运算越慢；float 用二进制近似十进制，0.1 + 0.2 != 0.3 不是 bug 而是表示法的必然' />

1. int 是变长 digit 数组、不溢出，位数越多越慢；3.11 起 int/str 互转默认限 4300 位

2. float 是 IEEE 754 双精度（符号 1 位、指数 11 位、尾数 52 位），用 math.isclose 比较

3. math.isclose 默认 rel_tol=1e-9、abs_tol=0.0；接近零时靠 abs_tol 兜底

[下一讲：字符串与编码：Unicode、str / bytes 与转义](/foundation/strings)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/008-numeric.py`

```bash
python3 examples/lessons/008-numeric.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/008-numeric.py) · [全部示例代码索引](/examples/)
