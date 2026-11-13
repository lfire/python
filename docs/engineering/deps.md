---
title: 第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建
description: 让任意机器构建出相同的环境
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='40 分钟' goal='让任意机器构建出相同的环境' prereq='第 071 讲 · 项目结构与 src 布局' />

# 第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建

> 依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；只写 requirements.txt 的宽泛范围做不到这点。本讲的目标是「让任意机器构建出相同的环境」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P072' title="本讲目标" :items='["能说清pyproject.toml 规范", "能说清直接与传递依赖", "能说清约束文件与锁", "能说清uv / poetry / pip-tools", "能说清哈希校验"]' />

## 1. 先建立直觉

**pyproject.toml 规范**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**直接与传递依赖**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**约束文件与锁**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

<ConceptDiagram type='layers3' title='第 072 讲 · pyproject.toml 规范' labels='pyproject.toml 规范|直接与传递依赖|约束文件与锁|uv / poetry / pip-tools' caption='让任意机器构建出相同的环境' />

上图用本讲的三个核心概念标出了主线：**pyproject.toml 规范 → 直接与传递依赖 → 约束文件与锁**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 pyproject.toml 规范 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 &gt;=3.10", "tone": "green"}, {"title": "深入边界", "desc": "厘清 直接与传递依赖 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 供应链安全 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**pyproject.toml 规范**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

```python
# pyproject.toml 片段（示意）
# [project]
# name = "demo"
# dependencies = ["httpx>=0.27"]
# [tool.pytest.ini_options]
# addopts = "-q"
import tomllib, pathlib
data = {"project": {"name": "demo", "requires-python": ">=3.10"}}
print(data["project"]["requires-python"])
```

<OutputBox title="运行结果" output='&gt;=3.10' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# pyproject.toml 片段（示意）\n# [project]\n# name = "demo"\n# dependencies = ["httpx&gt;=0.27"]\n# [tool.pytest.ini_options]\n# addopts = "-q"\nimport tomllib, pathlib\ndata = {"project": {"name": "demo", "requires-python": "&gt;=3.10"}}\nprint(data["project"]["requires-python"])' :notes='["pyproject.toml 是依赖与工具配置的唯一来源", "requires-python 明确解释器下界", "锁文件负责把依赖固定到具体版本", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**直接与传递依赖**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    db_url: str = "sqlite:///dev.db"
    debug: bool = False
print(Settings().model_dump())
```

<OutputBox title="对照写法的输出（先自己猜）" output='{&#39;db_url&#39;: &#39;sqlite:///dev.db&#39;, &#39;debug&#39;: False}' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# pyproject.toml 片段（示意）\n# [project]\n# name = \"demo\"\n# dependencies = [\"httpx&gt;=0.27\"]\n# [tool.pytest.ini_options]\n# addopts = \"-q\"\nimport tomllib, pathlib\ndata = {\"project\": {\"name\": \"demo\", \"requires-python\": \"&gt;=3.10\"}}\nprint(data[\"project\"][\"requires-python\"])", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from pydantic_settings import BaseSettings\nclass Settings(BaseSettings):\n    db_url: str = \"sqlite:///dev.db\"\n    debug: bool = False\nprint(Settings().model_dump())", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化」' />

## 3. 深入一步：规则与边界

**约束文件与锁**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**uv / poetry / pip-tools**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**哈希校验**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| pyproject.toml 规范 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化 |
| 直接与传递依赖 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化 |
| 约束文件与锁 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化 |
| uv / poetry / pip-tools | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化 |
| 哈希校验 | 这里的关键词是「什么时候」和「代价是什么」 | 开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化 |

<Term word='pyproject.toml 规范' text='依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；只写 requirements.txt 的宽泛范围做不到这点' />

<Callout type="warn" title="易错点" text='开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：pyproject.toml 规范", "body": "**pyproject.toml 规范**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：直接与传递依赖", "body": "**直接与传递依赖**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：约束文件与锁", "body": "**约束文件与锁**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：uv / poetry / pip-tools", "body": "**uv / poetry / pip-tools**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

提交锁文件、区分开发与运行依赖、CI 用 --require-hashes，并定期审计已知漏洞 **供应链安全**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -m compileall -q . && python -m pytest -q
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **pyproject.toml 规范** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「供应链安全」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「供应链安全」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 pyproject.toml 规范 与 供应链安全 两个关注点，并说明你的取舍。' :hints='["回到 pyproject.toml 规范 的规则", "留意易错点：开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化", "先让代码跑通，再补边界与异常分支"]' solution='from pydantic_settings import BaseSettings\nclass Settings(BaseSettings):\n    db_url: str = "sqlite:///dev.db"\n    debug: bool = False\nprint(Settings().model_dump())' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；提交锁文件、区分开发与运行依赖、CI 用 --require-hashes，并定期审计已知漏洞' />

## 随堂检测

<Quiz no='072-1' q='在本讲讨论的「pyproject.toml 规范」语境下，下面哪一种说法是准确的？' :options='["依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；只写 requirements.txt 的宽泛范围做不到这点", "pyproject.toml 规范 只影响代码的书写形式，不会改变任何运行时行为", "pyproject.toml 规范 在所有 Python 实现与所有版本中表现完全一致", "只要用了 pyproject.toml 规范，就不必再考虑 供应链安全 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 供应链安全 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='072-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["&gt;=3.10", "&gt;=3.10\n（无更多输出）", "AttributeError: pyproject.toml 规范 不可用"]' answer="0" output='&gt;=3.10' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='072-3' tpl='___tomllib, pathlib' :answers='["import"]' hint='回想本讲关于 pyproject.toml 规范 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["pyproject.toml 规范：pyproject.toml 规范", "直接与传递依赖：直接与传递依赖", "约束文件与锁：约束文件与锁", "uv / poetry / pip-tools：uv / poetry / pip-tools"]' :pitfalls='["开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化", "忽略版本差异，把 供应链安全 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；只写 requirements.txt 的宽泛范围做不到这点' />

## 小结与下一讲

1. pyproject.toml 规范：pyproject.toml 规范
2. 直接与传递依赖：直接与传递依赖
3. 提交锁文件、区分开发与运行依赖、CI 用 --require-hashes，并定期审计已知漏洞

[下一讲：代码规范：PEP 8、ruff、black 与 pre-commit](/engineering/style)
