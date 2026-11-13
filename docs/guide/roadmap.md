---
title: 第 005 讲 · 学习路线：十三个阶段如何递进
description: 理解阶段划分的依据与每阶段的出口能力
---

<StageHeader stage='L0 · 导学' level='★☆☆☆☆' time='20 分钟' goal='理解阶段划分的依据与每阶段的出口能力' prereq='第 004 讲 · 工具链全景：写代码、查问题、验质量' />

# 第 005 讲 · 学习路线：十三个阶段如何递进

地图铺开、工具也齐了，反倒想问：内容一大片，为什么偏按这个次序排，往后又把我带到哪。导学几讲走下来，Python 是什么、怎么跑、常用哪些命令都有了草图；这一讲就把这套学习路线的来龙去脉讲明白，让你知道自己在整张图上的位置。不少人想直接跳去学框架，或学了一阵说不清自己多会了什么。与其数『看了几讲』，不如先看阶段之间谁依赖谁——先写对再写快、先单进程再并发、先会写再发布；接着把每阶段该能交付的东西摆出来，用能否独立做出它当过关依据；最后聊认知负担的分界与打卡自检。带着前面几讲的印象就够；学完你能说清十三个阶段的先后道理，卡住时知道回头补哪节。


## 跳着学为什么会卡住：十三个阶段不是清单而是依赖图

一个自学者按博客顺序学：看完变量就直奔 Web 框架，照着教程能搭出页面，可一遇到登录装饰器就卡住，说不清它本质是函数替换；看到 ORM 的类能自动映射字段，也讲不出元类在导入时做了什么；等到给接口加线程池想提速反而更慢，GIL 三个字只背过结论。他于是回头补，却发现每补一个都要先补另一个，像拆一团互相打结的线。

另一个极端是有人把全部讲次当流水账从头刷到尾，刷完仍说不出「学完这一阶段我能交付什么」。朴素解法是「按顺序看一遍」或「用到再查」，两者都忽略了课程结构本身是一条依赖链：对象模型是描述符、元类、装饰器的前置，函数与闭包是装饰器的前置，迭代器与生成器是 `async/await` 的前置，进程与线程模型又是并发工程化的前置。

跳过任何一环，后面只能死记结论。本讲把「十三个阶段如何递进」落成一张可校验的依赖图，用环检测与拓扑排序证明顺序不是随意排的，并给出每阶段的出口能力。


## 先能对、再能快、先单进程、再并发

把每个阶段看成一个节点、把「必须先在前面掌握」的关系看成有向边，整门课就是一张有向无环图。导学没有前置，是唯一的根；编程地基依赖它，因为连变量是名字绑定都没弄清，就谈不上函数传参；容器与序列依赖地基的对象模型，list 里存的是引用、切片是副本，这些结论都从对象模型推出来；

函数与抽象同时依赖地基与容器两阶段，装饰器需要「函数是一等对象加闭包加可调用协议」，而推导式与迭代器是生成器表达式的语法基础。运行时与并发阶段依赖更深：描述符、元类依赖属性查找与 type，`async/await` 依赖迭代器与生成器（yield 把函数变成可暂停状态机），GIL 与进程池依赖对象头里的引用计数。

用 DFS 做环检测可以验证这张图没有循环依赖，用拓扑排序能算出合理的学习顺序；一旦有人把「并发」排在「函数」之前，图里就会出现无法先修的前置。那句「先能对，再能快；先单进程，再并发」正是这张图的文字版，不是鼓励式口号，而是偏序约束的自然结果。


## 阶段依赖与出口能力：用交付物定义进度

判断阶段是否走完，靠的是可交付物而不是打卡次数。导学的出口是能复现环境并解释源码到字节码的链路；地基的出口是能读 id、type、value，判断 is 与 ==，正确处理数值与编码；容器的出口是能按复杂度选 list、deque、dict、set 并用生成器处理大文件；

函数阶段的出口是能自己写出带 `functools.wraps` 的装饰器、理解闭包延迟绑定；

运行时阶段的出口是能用 importlib 与 inspect 定位导入问题、读懂类型注解契约；并发阶段的出口是能量化 CPU 与 IO 等待占比并选对线程池、进程池或 asyncio；工程化阶段的出口是能打包、写测试、接 CI。

把这些出口写成一张「阶段到能交付什么」的映射，就能给跳读者做自检：想直接学框架，先检查自己能否解释描述符与 GIL，缺哪项就回到对应节点补齐。所谓「跳读者用总目录补齐前置」，落到代码上就是对每个目标节点递归检查其所有依赖是否已被标记完成，把没完成的前置列出来，而不是笼统地劝人从头看。

```python
stages = {
    'L0': [],
    'L1': ['L0'],
    'L2': ['L1'],
    'L3': ['L1', 'L2'],
    'L4': ['L3'],
}

def has_cycle(graph):
    visiting, done = set(), set()
    def visit(node):
        if node in visiting: return True
        if node in done: return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if visit(dep): return True
        visiting.discard(node)
        done.add(node)
        return False
    return any(visit(n) for n in graph)

print('no_cycle', not has_cycle(stages))
print('stage_count', len(stages))
print('L3_needs', sorted(stages['L3']))
print('L0_is_root', stages['L0'] == [])
```

<OutputBox title='主示例运行结果' output='no_cycle True\nstage_count 5\nL3_needs [&#39;L1&#39;, &#39;L2&#39;]\nL0_is_root True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='stages = {\n    &#39;L0&#39;: [],\n    &#39;L1&#39;: [&#39;L0&#39;],\n    &#39;L2&#39;: [&#39;L1&#39;],\n    &#39;L3&#39;: [&#39;L1&#39;, &#39;L2&#39;],\n    &#39;L4&#39;: [&#39;L3&#39;],\n}\n\ndef has_cycle(graph):\n    visiting, done = set(), set()\n    def visit(node):\n        if node in visiting: return True\n        if node in done: return False\n        visiting.add(node)\n        for dep in graph.get(node, []):\n            if visit(dep): return True\n        visiting.discard(node)\n        done.add(node)\n        return False\n    return any(visit(n) for n in graph)\n\nprint(&#39;no_cycle&#39;, not has_cycle(stages))\nprint(&#39;stage_count&#39;, len(stages))\nprint(&#39;L3_needs&#39;, sorted(stages[&#39;L3&#39;]))\nprint(&#39;L0_is_root&#39;, stages[&#39;L0&#39;] == [])' :notes='["用邻接表表示阶段图：键是节点，值是它的直接前置列表", "L0 导学没有前置，是整张图的根", "L1 编程地基依赖 L0", "L2 容器依赖 L1 的对象模型", "L3 函数与抽象同时依赖 L1 与 L2，这是菱形共享前置", "L4 运行时依赖 L3", "字典闭合，图共 5 个节点", "定义环检测：输入邻接表，返回是否存在循环依赖", "visiting 记录当前递归栈上的节点，done 记录已完成节点", "内层递归函数 visit 判断从 node 出发能否走回栈上节点", "命中 visiting 说明出现回边，即存在循环依赖", "命中 done 说明该分支已确认无环，直接剪枝", "把当前节点压入递归栈", "遍历该节点的每个直接前置", "任一前置递归发现环就向上传播 True", "所有前置处理完，把节点移出递归栈", "标记该节点及其子图为已完成", "从该节点出发无环", "对每个节点启动一次 DFS，任一有环即返回 True", "本图无环，取 not 后打印 True", "打印节点总数，验证映射完整", "L3 的两个前置排序后打印，体现菱形依赖", "L0 的前置列表为空，证明它是根"]' title='第 005 讲 · 学习路线：十三个阶段如何递进' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**阶段依赖与出口能力**

| 阶段 | 直接前置 | 出口能力 |
| --- | --- | --- |
| L0 导学 | 无 | 复现环境、解释源码到字节码 |
| L1 编程地基 | L0 | 读 id/type/value、is 与 ==、数值与编码 |
| L2 容器与序列 | L1 | 按复杂度选容器、用生成器处理大文件 |
| L3 函数与抽象 | L1、L2 | 手写装饰器、理解闭包延迟绑定 |
| L4 运行时 | L1、L3 | 用 importlib/inspect 定位导入、读懂注解 |
| L5 并发 | L1、L4 | 量化等待占比、选对线程/进程/asyncio |


### 每个阶段的直接前置

节点的入边叫直接前置，和它的全部祖先是两回事：并发的直接前置是函数与抽象、运行时，导学只是传递前置。

`graphlib.TopologicalSorter` 的 `add(node, *predecessors)` 收的正是直接前置，`static_order()` 才给出不倒退的打卡顺序；

把整条祖先链都塞进去，图仍无环却多出冗余边，环检测信号也变模糊。Kahn 算法每次挑入度为 0 的节点，靠的也是只记入边的表。下表逐阶段列入边，缺哪条就先补哪讲，后面的环检测与拓扑对照才有着落。

**跃迁分界：从值到对象**

| 层面 | 关心的问题 | 可验证的属性或工具 |
| --- | --- | --- |
| 语言基础 | 值、流程、函数怎么算 | type、len、for |
| 对象模型 | 名字绑定到哪个对象 | id、is、__dict__ |
| 函数抽象 | 函数作为对象如何传递 | callable、__code__、__closure__、inspect.signature |
| 运行时 | 属性如何查找、类如何创建 | __get__、type、importlib |
| 并发 | 字节码如何被调度 | GIL、生成器状态机、线程池 |


## 认知负担与跃迁：从值到对象的分界

课程把最难的一次跃迁放在「语言基础到运行时」：前面写的是值、流程、函数，后面谈的是对象怎么被创建、属性怎么被查找、字节码怎么被执行。分界的根因是 Python 的统一对象模型——函数、类、模块、类型本身都是 PyObject，名字只是命名空间字典里的键。

装饰器之所以是「函数替换」而不是语法魔法，是因为函数在定义时就作为一个对象绑定到名字上，@ 只是把它传给另一个可调用对象再绑回原名；元类之所以能在类创建时改写属性，是因为 class 语句最终会调用 type；描述符之所以能拦截属性访问，是因为 `__get__` 与 `__set__` 是对象协议的一部分。

这些结论都能用 `inspect.signature`、`__code__`、callable、`__closure__` 这些标准属性当场验证，而不是靠背。

跳过地基直接学框架，遇到这三者只能记住「这么写就行」，一旦报错就无从推导。同理，生成器是 `async/await` 的基座：yield 把局部变量与指令指针留在帧里实现暂停恢复，协程只是把这套状态机接上事件循环。把跃迁拆成可验证的对象属性，认知负担才会从「一堆新名词」变成「一条推导链」。


### 装饰器、元类、描述符与 GIL 都从 PyObject 推导

四件事分属语法、类创建、属性与并发，共同根只是对象头的 ob_refcnt 与 ob_type：函数定义时就是带 `__code__`、可被 `callable()` 认出的对象，@ 才有得可传；class 最终调 type、属性走 `__get__`，都是类型协议；GIL 护的是引用计数不加细锁。

用 `type(f)`、`f.__closure__`、`inspect.signature` 可验，3.13 起 `sys._is_gil_enabled()` 让这层保护可选。

术语卡把对象头、可调用协议、引用计数并列。

<Term word='认知负担与阶段顺序' text='把每个阶段看成一个节点、把「必须先在前面掌握」的关系看成有向边，整门课就是一张有向无环图。导学没有前置，是唯一的根；编程地基依赖它，因为连变量是名字绑定都没弄清，就谈不上函数传参；容器与序列依赖地基的对象模型，list 里存的是引用、切片是副本，这些结论都从对象模型推出来；函数与抽象同时依赖地基与容器两阶段，装饰器需要' />

<Term word='语言基础到运行时的跃迁' text='判断阶段是否走完，靠的是可交付物而不是打卡次数。导学的出口是能复现环境并解释源码到字节码的链路；地基的出口是能读 id、type、value，判断 is 与 ==，正确处理数值与编码；容器的出口是能按复杂度选 list、deque、dict、set 并用生成器处理大文件；函数阶段的出口是能自己写出带 `functool' />


## 把学习顺序建模成有向无环图

<ConceptDiagram type='flow3' title='第 005 讲 · 阶段顺序是一条依赖图：先能对，再能快，再能并发' labels='阶段顺序是一条依赖图：先能对，再能快，再能并|出口能力：每个阶段交付什么，而不是读了多少页|认知负担与跃迁：为什么对象模型是绕不开的分界' caption='理解阶段划分的依据与每阶段的出口能力' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 环检测与拓扑排序对照

同一张图，环检测只答能不能排，拓扑排序要给出顺序。DFS 用白灰黑三色标记，碰到灰色回边即成环，后序逆序正好是拓扑序；Kahn 算法维护入度表，出队数少于节点总数就说明藏环。

两者都是 `O(V+E)`，失败信号却不同：`graphlib.TopologicalSorter.prepare()` 在 3.9 起遇环抛 CycleError，`args[1]` 给出环上节点，Kahn 只留数量缺口。

下表按判据、结构、失败信号、输出逐列对照，配 steps 走一遍建图到出序。

**环检测与拓扑排序对照**

| 算法 | 输入 | 输出 | 在本讲的用途 |
| --- | --- | --- | --- |
| DFS 环检测 | 依赖图 dict | 是否存在循环依赖 bool | 验证阶段顺序自洽 |
| 拓扑排序 | 依赖图 dict | 线性学习顺序 list | 给出打卡顺序 |
| 递归前置检查 | 目标节点加已完成集合 | 未完成前置列表 | 跳读者补齐依据 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：跳过对象模型直接学框架，遇到装饰器与元类就卡", "body": "装饰器依赖函数是一等对象与闭包，元类依赖 type 与属性查找，描述符依赖 __get__ 协议，这些都是地基阶段的结论", "tip": "回到地基用 callable、__code__、__closure__、inspect.signature 逐项验证，再回到框架代码"}, {"title": "第 2 步：把并发阶段排在函数与迭代器之前", "body": "async/await 建立在生成器暂停恢复之上，线程池与进程池又依赖对引用计数与 GIL 的理解，缺前置只能背结论", "tip": "按拓扑排序输出的学习顺序打卡，缺哪个节点先补哪个"}, {"title": "第 3 步：用「看了几讲」当作进度，说不出能交付什么", "body": "打卡次数是过程量，不能反映是否具备该阶段的出口能力", "tip": "给每阶段写一条可交付物，能独立做出该交付物才算通过"}]' />


## 用后序 DFS 输出不倒退的学习顺序

```python
graph = {'L0': [], 'L1': ['L0'], 'L2': ['L1'], 'L3': ['L1', 'L2']}
order, seen = [], set()
def emit(n):
    if n in seen: return
    for d in graph[n]: emit(d)
    seen.add(n); order.append(n)
for n in graph: emit(n)
print('order', order)
print('L1_before_L3', order.index('L1') < order.index('L3'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='order [&#39;L0&#39;, &#39;L1&#39;, &#39;L2&#39;, &#39;L3&#39;]\nL1_before_L3 True' guess="true" />


## 为什么对象模型不能跳过：底层依赖链

阶段依赖本质是偏序关系：若 A 是 B 的前置，则 A 必须排在 B 之前，但兄弟节点之间没有先后约束。用邻接表（dict 映射节点到前置列表）表示这张有向图，DFS 环检测靠两个集合：visiting 标记当前递归栈上的节点，done 标记已完成节点；

进入节点先查 visiting，命中说明出现回边即有环，查 done 则直接剪枝。之所以要区分「栈上」与「已完成」，是因为只有回到栈上节点才是环，回到已完成的旁支只是共享前置，有向无环图允许菱形依赖，例如 L3 同时依赖 L1 与 L2。

拓扑排序用后序 DFS：先把所有前置递归输出，再把自己追加到 order，这样任何节点出现时它的前置都已在列表里。对象模型能作为绝大多数高级特性的前置，原因是 CPython 把函数实现为 PyFunctionObject、把类实现为 type 的实例，二者都带 `__dict__` 与标准协议方法；

`inspect.signature` 读的是 `__code__` 与 `__defaults__`，callable 查的是类型是否实现 tp_call。

于是「装饰器是函数替换」「元类拦截类创建」都不是孤立语法，而是同一套对象协议在不同层面的应用，这也决定了跳过地基就无法推导后面任何一环。


## 跳读者前置自检器：把「补齐前置」变成可计算的结果

一个想直接学 Web 框架的读者，最需要的不是劝他从头看，而是一份明确的清单：目标阶段到底依赖哪些节点、其中哪些还没完成、以及学完之后应当能交付什么。下面这段把课程结构写成邻接表，用递归 prereqs 收集目标节点的全部传递前置，用 DFS 环检测确认依赖图自洽，再把「已完成集合」与「所需前置」做差集得到缺失清单。

真实教学平台可以把它接到打卡记录上：用户点选目标章节，页面直接列出必须先补的章节与每章的出口描述，而不是给一句笼统的建议。重点在于把「顺序是设计出来的」这件事变成可运行的校验，任何一条新增依赖若引入环，自检会立刻报出来。

```python
GRAPH = {
    'L0': [], 'L1': ['L0'], 'L2': ['L1'],
    'L3': ['L1', 'L2'], 'L4': ['L1', 'L3'], 'L5': ['L1', 'L4'],
}

def prereqs(node, graph, seen=None):
    if seen is None:
        seen = set()
    for dep in graph.get(node, []):
        if dep not in seen:
            seen.add(dep)
            prereqs(dep, graph, seen)
    return seen

def has_cycle(graph):
    visiting, done = set(), set()
    def visit(n):
        if n in visiting: return True
        if n in done: return False
        visiting.add(n)
        if any(visit(d) for d in graph.get(n, [])):
            return True
        visiting.discard(n); done.add(n)
        return False
    return any(visit(n) for n in graph)

def plan(target, completed):
    need = prereqs(target, GRAPH)
    return {'acyclic': not has_cycle(GRAPH),
            'missing': sorted(need - set(completed)),
            'total': len(need)}

r = plan('L5', ['L0', 'L1'])
print('acyclic', r['acyclic'])
print('missing', r['missing'])
print('total', r['total'])
```

<Callout type="idea" title='落地提示' text='每个阶段都有明确的出口能力（能交付什么），建议按顺序打卡，跳读者用总目录补齐前置' />


## 打卡次数不是能力：排错的三个信号

进度条走完却说不出能力，有三个可观察信号：被问某阶段交付物时只能报讲次，比如地基阶段本该能解释 is 与 ==、写出带 `functools.wraps` 的装饰器；

遇描述符或 GIL 报错只能搜，不会用 callable、`__closure__` 从对象模型往下推；做综合项目反复跳回补前置，说明拓扑序没走完。给每阶段写一条可交付物再打勾，跳读者对目标节点递归查祖先是否标完成，比数讲次可靠。下表按现象、根因、补法列这三个信号。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 跳过对象模型直接学框架，遇到装饰器与元类就卡住 | 装饰器依赖函数是一等对象与闭包，元类依赖 type 与属性查找，描述符依赖 __get__ 协议，这些都是地基阶段的结论 | 回到地基用 callable、__code__、__closure__、inspect.signature 逐项验证，再回到框架代码 |
| 把并发阶段排在函数与迭代器之前 | async/await 建立在生成器暂停恢复之上，线程池与进程池又依赖对引用计数与 GIL 的理解，缺前置只能背结论 | 按拓扑排序输出的学习顺序打卡，缺哪个节点先补哪个 |
| 用「看了几讲」当作进度，说不出能交付什么 | 打卡次数是过程量，不能反映是否具备该阶段的出口能力 | 给每阶段写一条可交付物，能独立做出该交付物才算通过 |

<Callout type="warn" title='本讲最容易踩的坑' text='跳过对象模型直接学框架，遇到装饰器与元类就卡住：装饰器依赖函数是一等对象与闭包，元类依赖 type 与属性查找，描述符依赖 __get__ 协议，这些都是地基阶段的结论' />


## 用拓扑序自检：练习、自测与速记

<Exercise title='基础：给依赖图做环检测' task='实现 has_cycle(graph)，用 DFS 与 visiting/done 两个集合判断阶段图是否有循环依赖，并在人为给根节点加一条回边后返回 True。' solution='def has_cycle(graph):\n    visiting, done = set(), set()\n    def visit(n):\n        if n in visiting: return True\n        if n in done: return False\n        visiting.add(n)\n        for d in graph.get(n, []):\n            if visit(d): return True\n        visiting.discard(n); done.add(n)\n        return False\n    return any(visit(n) for n in graph)\ng = {&#39;L0&#39;: [], &#39;L1&#39;: [&#39;L0&#39;], &#39;L2&#39;: [&#39;L1&#39;]}\nprint(&#39;clean&#39;, not has_cycle(g))\ng[&#39;L0&#39;] = [&#39;L2&#39;]\nprint(&#39;with_backedge&#39;, has_cycle(g))' explain='干净图无环返回 False；给 L0 加上指向 L2 的回边后，DFS 会走回递归栈上的节点，visiting 命中即判为有环。' />

<Exercise title='进阶：拓扑排序输出学习顺序' task='写 topo(graph) 返回线性顺序，使每个节点都排在其所有前置之后；用菱形依赖图（L3 依赖 L1 与 L2）验证两个前置都排在 L3 之前。' solution='def topo(graph):\n    order, seen = [], set()\n    def emit(n):\n        if n in seen: return\n        for d in graph.get(n, []): emit(d)\n        seen.add(n); order.append(n)\n    for n in graph: emit(n)\n    return order\ng = {&#39;L0&#39;: [], &#39;L1&#39;: [&#39;L0&#39;], &#39;L2&#39;: [&#39;L1&#39;], &#39;L3&#39;: [&#39;L1&#39;, &#39;L2&#39;]}\no = topo(g)\nprint(&#39;order&#39;, o)\nprint(&#39;deps_before&#39;, o.index(&#39;L1&#39;) &lt; o.index(&#39;L3&#39;) and o.index(&#39;L2&#39;) &lt; o.index(&#39;L3&#39;))' explain='后序 DFS 保证先输出前置再输出自身，因此 L1 与 L2 都排在 L3 前；菱形共享前置在 DAG 里合法，不会被误判成环。' />

<Quiz no='005-1' q='关于十三个阶段的顺序，哪项描述准确？' :options='["它是一条有向无环图：装饰器依赖函数一等对象与闭包，async/await 依赖生成器", "各阶段互相独立，顺序可以随意打乱", "并发应排在函数之前，因为更常用", "跳过对象模型不影响理解元类"]' answer="0" explain='阶段按依赖关系排布，描述符、元类、装饰器从对象模型推导，协程建立在生成器状态机上；跳过前置只能死记结论，无法自己推导。' />

<Quiz no='005-2' q='DFS 环检测里为什么要同时用 visiting 与 done 两个集合？' :options='["只有回到递归栈上的节点才是环，回到已完成旁支只是共享前置", "为了加快遍历速度", "visiting 存结果、done 存输入", "Python 的集合不能单独使用"]' answer="0" explain='visiting 标记当前路径，命中才是回边；done 标记确认无环的子图，用于剪枝。菱形依赖会多次到达同一节点，但那不是环。' />

<Quiz no='005-3' q='判断某阶段是否走完，最合理的依据是？' :options='["能否独立交付该阶段的出口能力，而不是看了几讲", "打卡次数", "笔记字数", "是否记住了所有 API 名称"]' answer="0" explain='出口能力是可交付物（如能手写装饰器、能量化等待占比），过程量如打卡次数与笔记字数都不能证明具备该能力。' />

<Predict no='005-4' q='主示例里 print(&#39;no_cycle&#39;, not has_cycle(stages)) 输出什么？' :options='["no_cycle True", "no_cycle False", "抛出 RecursionError"]' answer='0' output='no_cycle True' explain='stages 是排好的无环依赖图，DFS 不会在 visiting 集合里遇到回边，has_cycle 返回 False，取 not 得到 True；菱形共享前置由 done 剪枝，不算环。' />

<FillBlank no='005-5' tpl='___ has_cycle(graph):' :answers='["def"]' hint='回想本讲关于 认知负担与阶段顺序 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 阶段顺序是一条依赖图：先能对，再能快，再能并发 的落点。' />

<KnowledgeCard :points='["十三个阶段是一条有向无环图：先能对、再能快、先单进程、再并发、最后谈架构与源码", "DFS 环检测用 visiting（递归栈）与 done（已完成）两集合，菱形共享前置不算环", "拓扑排序用后序 DFS，输出顺序保证每个节点的所有前置都排在它前面", "对象模型是绕不开的分界：装饰器、元类、描述符、GIL 都从 PyObject 推导", "async/await 建立在生成器暂停恢复之上；并发依赖对引用计数与 GIL 的理解", "用出口能力（能交付什么）判断阶段是否通过，打卡次数只是过程量"]' :pitfalls='["跳过对象模型直接学框架，遇到装饰器与元类就卡住", "把并发阶段排在函数与迭代器之前", "用「看了几讲」当作进度，说不出能交付什么", "跳过对象模型直接学框架，遇到描述符、元类、GIL 时只能死记结论，无法自己推导"]' summary='阶段顺序按依赖设计：先能对，再能快；先单进程，再并发；先会写，再会发布；最后才谈架构与源码' />

1. 十三个阶段是一条有向无环图：先能对、再能快、先单进程、再并发、最后谈架构与源码

2. DFS 环检测用 visiting（递归栈）与 done（已完成）两集合，菱形共享前置不算环

3. 拓扑排序用后序 DFS，输出顺序保证每个节点的所有前置都排在它前面

[下一讲：一切皆对象：id、type、value 与可变性](/foundation/object-model)
