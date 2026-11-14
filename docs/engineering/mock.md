---
title: 第 076 讲 · Mock 与测试替身：时间、网络与随机
description: 让不可控依赖变得可测
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='35 分钟' goal='让不可控依赖变得可测' prereq='第 075 讲 · 单元测试：pytest、fixture 与参数化' />

# 第 076 讲 · Mock 与测试替身：时间、网络与随机

测试骨架有了，可一旦依赖时间、网络或随机，用例就开始看运气。一个「验证码五分钟过期」的测试白天全过、夜里偶发失败，查下来是有人改了全局时钟又没收回；更常见的是替身打在了名字定义的地方，业务照旧读真实时间，测试却显示通过。

从 `unittest.mock` 与 patch 该打在哪儿说起，走到 monkeypatch，再用时钟注入、freezegun 与 `HTTP` 假实现把不可控依赖包起来，接着分清桩、假对象与间谍，最后落到依赖注入。带着测试、fixture 与导入解析的底子来；学完能把时间、随机、网络封成可注入依赖，优先用假实现，写出不串味的测试。


## 「验证码 5 分钟过期」的测试白天全过、夜里偶发失败

一个「验证码 5 分钟过期」的测试白天全过、夜里偶发失败；

排查发现测试用 `freezegun.freeze_time` 改了全局 datetime，却没限制作用域，另一个并发用例把时间又改了回去。

更常见的一类：服务里写 `from clock import now`，测试照着「定义处」去 patch `clock.now`，结果业务函数照样读真实时间——patch 打错了位置，测试却显示通过。

还有人在断言里把 `assert_called_once_with` 拼成 `assret_called_once_with`，MagicMock 默默造出这个属性，测试永远绿。

这些失败都指向同一件事：替身要打在名字被查找的地方，且可控依赖最好通过注入传入。本讲把 `unittest.mock` 的 patch 位置、时间/随机/网络的假实现，以及替身分类讲到能写出不串味的测试。

<Callout type="warn" title='先看一个真实会出错的写法' text='patch 打在「定义处」而非「使用处」：from clock import now 会在业务模块绑定独立名字，改 clock.now 不影响它' />


## patch 要打在「被使用的地方」：定义处 vs 使用处

`unittest.mock` 提供 Mock、MagicMock、`patch` / `patch.object` / `patch.dict`，可作装饰器或上下文管理器，常用参数 `return_value`、`side_effect`（异常或序列）、`autospec`、`spec`；

断言用 `assert_called_once_with`、`call_count`、`reset_mock`。

决定成败的是 patch 目标：应打在「名字被查找的地方」而不是「定义的地方」。

若 `service.py` 写 `from clock import now`，则 service 模块里绑定了 `service.now` 这个名字，patch `clock.now` 只改了 clock 模块的引用，`service.greet()` 仍读旧函数；

必须 patch `service.now` 才生效（可验证：定义处 patch 后仍返回 real，使用处 patch 才返回 `FAKE`）。反过来若业务写 `import clock` 再 `clock.now()`，就 patch `clock.now`。

patch 在退出时用保存的原值还原，`patch.dict` 可对 `os.environ` 做临时替换。

**patch 目标选择：定义处 vs 使用处**

| 业务写法 | 名字被查找处 | 应 patch 的目标 |
| --- | --- | --- |
| from clock import now; now() | service.now | service.now |
| import clock; clock.now() | clock.now | clock.now |
| from pkg import util; util.f() | 当前模块的 util | 当前模块.util.f 或 util.f |
| from datetime import datetime | 当前模块的 datetime | 当前模块.datetime |
| 读 os.environ['K'] | os.environ | patch.dict(os.environ, &#123;'K': 'v'&#125;) |

<Callout type="tip" title='核心心智模型' text='`unittest.mock` 提供 Mock、MagicMock、`patch` / `patch.object` / `patch.dict`，可作装饰器或上下文管理器，常用参数 `return_value`、`side_effect`（异常或序列）、`autospec`、`spec`；断言用…' />

`unittest.mock.patch` 把目标字符串按最后一个点拆成「模块/对象 + 属性」，import 该模块后对其 setattr 保存原值并替换成 MagicMock，退出时用 `__exit__` 把原值写回；

因此 patch `clock.now` 只改 clock 模块字典，而 `service.py` 早用 `from clock import now` 把函数对象绑成了自己的 `service.now`，二者是不同命名空间里的两个名字，改前者不影响后者——这就是「patch 打在使用处」的底层原因。

`MagicMock.__getattr__` 对未知属性返回一个新的子 Mock，所以拼错的断言方法不会触发 AttributeError；

`create_autospec` 从目标类的 `__init__` / 方法签名构造 spec，`__getattr__` 对不在 spec 里的名字抛 AttributeError。

freezegun 的做法是把 `sys.modules` 里的 datetime、date、time 等替换成 FrozenDateTime 家族，属全局改动，故必须用上下文限定作用域或改用构造函数注入的 now callable。

`random.Random(seed)` 是独立的 Mersenne Twister 实例，同 seed 同调用序列可复现，因此注入它比 patch random 全局更隔离。

<ConceptDiagram type='flow4' title='第 076 讲 · unittest.mock 与 patch 位置' labels='unittest.mock 与 patch…|时间、随机、网络的可控注入|测试替身分类与 autospec 防呆|依赖注入' caption='让不可控依赖变得可测' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 为什么 patch 定义处常常不生效

```python
from unittest.mock import Mock, create_autospec

class Service:
    def fetch(self, key):
        return 'real'

m = Mock()
print('bare mock invents attr', hasattr(m, 'fetchh'))
m.fetchh()
safe = create_autospec(Service, instance=True)
try:
    safe.fetchh()
except AttributeError:
    print('autospec rejects typo', True)
safe.fetch.return_value = 'fake'
print('autospec call ok', safe.fetch('k'))
```

<OutputBox title='原理验证' output='bare mock invents attr True\nautospec rejects typo True\nautospec call ok fake' />

<Term word='unittest.mock 与 patch 位置' text='`unittest.mock` 提供 Mock、MagicMock、`patch` / `patch.object` / `patch.dict`，可作装饰器或上下文管理器，常用参数 `return_value`、`side_effect`（异常或序列）、`autospec`、`spec`；断言用…' />

<Term word='monkeypatch' text='时间最稳的做法是依赖注入：把 now 这个 callable 作为函数参数或对象构造参数传入，测试传一个返回固定值的 FakeClock，而不是全局 patch `datetime.datetime.now`；`freezegun.freeze_time` 之所以方便，是因为它替换 `sys.modules` 里的 d…' />


## 对照：patch 使用处与定义处的输出差

```python
import sys, os, tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'clock.py'), 'w').write('def now():' + chr(10) + '    return "real"' + chr(10))
    open(os.path.join(d, 'service.py'), 'w').write('from clock import now' + chr(10) + 'def greet():' + chr(10) + '    return "hi " + now()' + chr(10))
    sys.path.insert(0, d)
    import service, clock
    print('baseline', service.greet())

    with patch.object(clock, 'now', return_value='FAKE'):
        print('patch definition site', service.greet())

    with patch.object(service, 'now', return_value='FAKE'):
        print('patch use site', service.greet())
    sys.path.remove(d)
```

<OutputBox title='主示例运行结果' output='baseline hi real\npatch definition site hi real\npatch use site hi FAKE' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, os, tempfile\nfrom unittest.mock import patch\n\nwith tempfile.TemporaryDirectory() as d:\n    open(os.path.join(d, &#39;clock.py&#39;), &#39;w&#39;).write(&#39;def now():&#39; + chr(10) + &#39;    return "real"&#39; + chr(10))\n    open(os.path.join(d, &#39;service.py&#39;), &#39;w&#39;).write(&#39;from clock import now&#39; + chr(10) + &#39;def greet():&#39; + chr(10) + &#39;    return "hi " + now()&#39; + chr(10))\n    sys.path.insert(0, d)\n    import service, clock\n    print(&#39;baseline&#39;, service.greet())\n\n    with patch.object(clock, &#39;now&#39;, return_value=&#39;FAKE&#39;):\n        print(&#39;patch definition site&#39;, service.greet())\n\n    with patch.object(service, &#39;now&#39;, return_value=&#39;FAKE&#39;):\n        print(&#39;patch use site&#39;, service.greet())\n    sys.path.remove(d)' :notes='["导入 sys/os/tempfile 建临时模块，patch 做替换", "从 unittest.mock 取 patch.object", "空行，只用于分隔逻辑块，不影响执行结果。", "临时目录里造两个模块模拟业务与依赖", "clock.py 定义 now 返回 real", "service.py 用 from clock import now 绑定本地名字", "把临时目录加入 sys.path 以便 import", "导入两个模块，service.now 此刻指向原函数", "基线：greet 读到真实时间 real", "空行，只用于分隔逻辑块，不影响执行结果。", "尝试在「定义处」clock 模块上 patch now", "service.greet 仍读自己的 service.now，故还是 real", "空行，只用于分隔逻辑块，不影响执行结果。", "改在「使用处」service 模块上 patch now", "这次 greet 读到 FAKE，patch 生效", "移除临时路径，环境干净"]' title='第 076 讲 · Mock 与测试替身：时间、网络与随机' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import random

class FakeClock:
    def __init__(self, start):
        self.t = start
    def now(self):
        self.t += 1
        return self.t

class FakeRNG:
    def __init__(self, values):
        self.values = list(values)
    def randrange(self, n):
        return self.values.pop(0) % n

def make_id(clock, rng):
    return str(clock.now()) + '-' + str(rng.randrange(100))

c = FakeClock(100)
r = FakeRNG([7, 7, 7])
print('id1', make_id(c, r))
print('id2', make_id(c, r))
print('clock advanced', c.t)
print('seeded reproducible', random.Random(7).randrange(100) == random.Random(7).randrange(100))
```

<OutputBox title='对照写法：先自己猜，再点开' output='id1 101-7\nid2 102-7\nclock advanced 102\nseeded reproducible True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import sys, os, tempfile\nfrom unittest.mock import patch\n\nwith tempfile.TemporaryDirectory() as d:\n    open(os.path.join(d, &#39;clock.py&#39;), &#39;w&#39;).write(&#39;def now():&#39; + chr(10) + &#39;    return \"real\"&#39; + chr(10))\n    open(os.path.join(d, &#39;service.py&#39;), &#39;w&#39;).write(&#39;from clock import now&#39; + chr(10) + &#39;def greet():&#39; + chr(10) + &#39;    return \"hi \" + now()&#39; + chr(10))\n    sys.path.insert(0, d)\n    import service, clock\n    print(&#39;baseline&#39;, service.greet())\n\n    with patch.object(clock, &#39;now&#39;, return_value=&#39;FAKE&#39;):\n        print(&#39;patch definition site&#39;, service.greet())\n\n    with patch.object(service, &#39;now&#39;, return_value=&#39;FAKE&#39;):\n        print(&#39;patch use site&#39;, service.greet())\n    sys.path.remove(d)", "note": "unittest.mock 与 patch 位置"}, {"label": "对照 / 进阶", "code": "import random\n\nclass FakeClock:\n    def __init__(self, start):\n        self.t = start\n    def now(self):\n        self.t += 1\n        return self.t\n\nclass FakeRNG:\n    def __init__(self, values):\n        self.values = list(values)\n    def randrange(self, n):\n        return self.values.pop(0) % n\n\ndef make_id(clock, rng):\n    return str(clock.now()) + &#39;-&#39; + str(rng.randrange(100))\n\nc = FakeClock(100)\nr = FakeRNG([7, 7, 7])\nprint(&#39;id1&#39;, make_id(c, r))\nprint(&#39;id2&#39;, make_id(c, r))\nprint(&#39;clock advanced&#39;, c.t)\nprint(&#39;seeded reproducible&#39;, random.Random(7).randrange(100) == random.Random(7).randrange(100))", "note": "时间、随机、网络的可控注入"}]' title='两种写法对照' note='差异集中在 unittest.mock 与 patch 位置；先看输出，再找背后的规则。' />

**unittest.mock 常用 API**

| API | 作用 | 边界 |
| --- | --- | --- |
| Mock / MagicMock | 通用替身，MagicMock 支持魔法方法 | 任意属性动态创建，拼错名不报错 |
| patch(target) / patch.object | 临时替换属性并自动还原 | target 要是「被查找处」 |
| return_value / side_effect | 固定返回 / 异常或序列 | side_effect 可为可迭代对象 |
| assert_called_once_with | 校验调用参数 | 过度使用会绑死实现 |
| spec / autospec / create_autospec | 按真实签名限制属性 | 访问不存在方法抛 AttributeError |
| seal() (3.7+) | 冻结已访问属性 | 防止后续拼错名 |
| monkeypatch (pytest) | setattr/setenv/chdir 且自动 undo | function 级，无需手动还原 |


## 时间、随机、网络的可控注入与替身分类

时间最稳的做法是依赖注入：把 now 这个 callable 作为函数参数或对象构造参数传入，测试传一个返回固定值的 FakeClock，而不是全局 patch `datetime.datetime.now`；

`freezegun.freeze_time` 之所以方便，是因为它替换 `sys.modules` 里的 datetime/date/time 等模块，但全局修改会串味，必须限定作用域。

随机用 `random.Random(seed)` 实例注入或传入一个按序取值的 FakeRNG，固定 seed 的结果可复现（同 seed 两次 randrange 相等）；

真正的安全令牌仍用 `secrets`。

网络用 `httpx.MockTransport`、responses 或注入一个带 get 方法的 FakeHTTP，返回预置页面并记录调用。

优先用有真实行为的假实现（fake）而不是深度断言调用次数：前者验证外部行为，后者把测试绑死在内部实现上。

替身按职责分五类：dummy 只占位不被用、stub 返回固定值、spy 记录调用、mock 预设期望并校验调用、fake 是有可用行为的轻量实现（内存版仓储、假时钟）。依赖注入让时间、随机、网络都成为可替换参数，测试不再依赖全局状态，因而不会跨用例串味。

`MagicMock.__getattr__` 会为任意属性动态造子 Mock，把 `assert_called_once_with` 拼成 `assret_called_once_with` 不会报错，测试假通过；

用 `spec=`、`autospec=True` 或 `create_autospec` 让对象按真实签名生成，访问不存在的方法就抛 AttributeError（可验证：裸 Mock 上 `hasattr(m,'fetchh')` 为 True，autospec 拒绝拼错名）。

3.7 起的 `seal()` 还能冻结已访问属性，防止后续拼错。pytest 的 monkeypatch 与 patch 等价且自动 undo，适合函数级临时替换。

**测试替身分类**

| 类型 | 行为 | 适用 |
| --- | --- | --- |
| dummy | 占位、不被真正使用 | 凑参数 |
| stub | 返回预置固定值 | 隔离外部查询 |
| spy | 记录调用供检查 | 验证交互次数（谨慎用） |
| mock | 预设期望并校验调用 | 契约型交互 |
| fake | 有可用行为的轻量实现 | 内存仓储、假时钟、假 HTTP（推荐） |

```bash
python -m pytest -q --disable-warnings
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `unittest.mock` 与 patch 位置 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 依赖注入让时间、网络、随机全部可控

把不可控依赖变成可注入参数，是替身最稳的形态：服务函数接收 http、clock、rng 三个对象，测试时传入 FakeHTTP（预置页面并记录调用）、FakeClock（固定递增时间）、`random.Random(seed)`（可复现随机），生产时换真实实现。

这样测试不修改任何全局对象，跨用例零串味，且验证的是「按 URL 抓取并生成记录」这个外部行为而非内部调用次数。下面片段用标准库拼出这套注入结构并打印行数、调用轨迹与时钟终值。

```python
import random

class FakeHTTP:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
    def get(self, url):
        self.calls.append(url)
        return self.pages.get(url, '')

class Clock:
    def __init__(self, start=0):
        self.t = start
    def now(self):
        self.t += 1
        return self.t

def collect(http, clock, rng, urls):
    rows = []
    for url in urls:
        body = http.get(url)
        rows.append((url, len(body), clock.now(), rng.randrange(1000)))
    return rows

http = FakeHTTP({'/a': 'alpha', '/b': 'beta'})
clock = Clock(100)
rng = random.Random(7)
rows = collect(http, clock, rng, ['/a', '/b', '/missing'])
print('rows', len(rows))
print('http calls', http.calls)
print('clock end', clock.t)
print('seeded reproducible', random.Random(7).randrange(1000) == random.Random(7).randrange(1000))
```

<Callout type="idea" title='落地提示' text='把时间、随机、网络封装成可注入依赖，优先用假实现（fake）而不是深度断言调用次数' />

<CheckList id='P076b' title='上线前自检' :items='["能复现并解释「patch 打在「定义处」而非「使用处」」", "能复现并解释「mock 了不存在的方法、或把断言方法名拼错」", "能复现并解释「全局 patch datetime.now / random…」", "能用一条命令验证 unittest.mock 与 patch 位置", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| patch 打在「定义处」而非「使用处」 | from clock import now 会在业务模块绑定独立名字，改 clock.now 不影响它 | 定位名字被查找的模块，patch service.now；写 import clock 时才 patch clock.now |
| mock 了不存在的方法、或把断言方法名拼错 | MagicMock.__getattr__ 为任意属性动态造子 Mock，assret_called_once_with 静默通过 | 用 spec / autospec / create_autospec 按真实签名限制，或 seal() 冻结属性 |
| 全局 patch datetime.now / random 且不限制作用域 | 修改 sys.modules 级全局对象，跨用例串味、时区与异步任务互相干扰 | 把 now / rng / http 作为依赖注入传入 Fake 实现；freezegun 必须限定 with 作用域 |

<Callout type="warn" title='本讲最容易踩的坑' text='patch 打在「定义处」而非「使用处」：from clock import now 会在业务模块绑定独立名字，改 clock.now 不影响它' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：patch 打在「定义处」而非「使用处」", "body": "from clock import now 会在业务模块绑定独立名字，改 clock.now 不影响它", "tip": "定位名字被查找的模块，patch service.now；写 import clock 时才 patch clock.now"}, {"title": "第 2 步：mock 了不存在的方法、或把断言方法名拼错", "body": "MagicMock.__getattr__ 为任意属性动态造子 Mock，assret_called_once_with 静默通过", "tip": "用 spec / autospec / create_autospec 按真实签名限制，或 seal() 冻结属性"}, {"title": "第 3 步：全局 patch datetime.now…", "body": "修改 sys.modules 级全局对象，跨用例串味、时区与异步任务互相干扰", "tip": "把 now / rng / http 作为依赖注入传入 Fake 实现；freezegun 必须限定 with 作用域"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：确认 patch 上下文自动还原' task='用 patch.object 临时把 os.sep 改成 &#39;X&#39;，退出 with 后打印 os.sep != &#39;X&#39; 证明还原。' solution='from unittest.mock import patch\nimport os\nwith patch.object(os, &#39;sep&#39;, &#39;X&#39;):\n    print(&#39;patched&#39;, os.sep)\nprint(&#39;restored&#39;, os.sep != &#39;X&#39;)' explain='patch 保存原值并在 __exit__ 写回，等价于 monkeypatch 的自动 undo；用例之间不会残留被改的全局属性。' />

<Exercise title='进阶：注入固定时钟' task='定义一个 now() 返回固定值的 Clock，作为依赖传给被测函数并打印结果，说明为何不全局 patch datetime。' solution='class Clock:\n    def __init__(self, v):\n        self.v = v\n    def now(self):\n        return self.v\nc = Clock(100)\nprint(&#39;deterministic&#39;, c.now() == 100)' explain='把 now 作为可注入依赖，测试传固定实现即可；不修改 sys.modules 里的 datetime，避免全局串味与时区问题。' />

<Quiz no='076-1' q='service.py 写 from clock import now，测试要替换 now 应 patch 哪里？' :options='["service.now（名字被查找处）", "clock.now（定义处）", "两者都要", "builtins.now"]' answer="0" explain='from X import y 会在当前模块绑定独立名字 service.now；patch clock.now 只改 clock 模块字典，不影响 service 已绑定的引用，必须打在使用处。' />

<Quiz no='076-2' q='裸 MagicMock 上把断言拼成 assret_called_once_with 会？' :options='["静默通过，因 __getattr__ 动态造出该属性", "抛 AttributeError", "抛 TypeError", "自动更正拼写"]' answer="0" explain='MagicMock.__getattr__ 对任意名字返回新的子 Mock，拼错名不报错，测试假通过；用 spec/autospec/create_autospec 让未知属性抛 AttributeError。' />

<Quiz no='076-3' q='关于时间替身，最稳妥的做法是？' :options='["把 now callable 注入被测对象，测试传 FakeClock", "全局 patch datetime.datetime.now", "直接改系统时间", "在测试里 sleep 到指定时间"]' answer="0" explain='注入固定时钟不修改任何全局对象，跨用例零串味；freezegun 替换 sys.modules 属全局改动，必须严格限定 with 作用域。' />

<Predict no='076-4' q='service.py 里 from clock import now; def greet(): return &#39;hi &#39; + now()，测试用 patch.object(clock,&#39;now&#39;,return_value=&#39;X&#39;) 后 greet() 返回？' :options='["hi real（原值，patch 未生效）", "hi X", "AttributeError"]' answer='0' output='hi real（原值，patch 未生效）' explain='service 通过 from clock import now 把函数绑定成自己的 service.now；patch clock.now 改的是 clock 模块字典，service 仍读旧引用。应改 patch service.now。' />

<FillBlank no='076-5' tpl='___ sys, os, tempfile' :answers='["import"]' hint='回想本讲关于 unittest.mock 与 patch 位置 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 unittest.mock 与 patch 位置 的落点。' />

<KnowledgeCard :points='["patch 要打在名字被查找处：from clock import now 要 patch 当前模块.now，import clock 才 patch clock.now", "patch 保存原值、退出自动还原；patch.dict 可临时替换 os.environ", "时间/随机/网络优先依赖注入：FakeClock、random.Random(seed)、FakeHTTP，避免全局修改", "MagicMock.__getattr__ 动态造属性，拼错断言方法会假通过；用 spec/autospec/create_autospec 或 seal()", "替身分类：dummy/stub/spy/mock/fake；优先 fake（有行为的轻量实现）而非深度调用断言", "freezegun 替换 sys.modules 里 datetime/date/time，属全局改动，必须用 with 限定作用域"]' :pitfalls='["patch 打在「定义处」而非「使用处」", "mock 了不存在的方法、或把断言方法名拼错", "全局 patch datetime.now / random 且不限制作用域", "mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现"]' summary='patch 要打在「被使用的地方」而不是「定义的地方」，这个细节占了 mock 失败案例的一大半' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| patch 要打在名字被查找处：from clock import now 要 patch 当前模块.now，import clock 才 patch clock.now | 建立直觉 |
| patch 保存原值、退出自动还原；patch.dict 可临时替换 os.environ | 跑通示例 |
| 时间/随机/网络优先依赖注入：FakeClock、random.Random(seed)、FakeHTTP，避免全局修改 | 深入边界 |
| MagicMock.__getattr__ 动态造属性，拼错断言方法会假通过；用 spec/autospec/create_autospec 或 seal() | 工程落地 |
| 替身分类：dummy/stub/spy/mock/fake；优先 fake（有行为的轻量实现）而非深度调用断言 | 随堂检测 |
| freezegun 替换 sys.modules 里 datetime/date/time，属全局改动，必须用 with 限定作用域 | 复盘 |

1. patch 要打在名字被查找处：from clock import now 要 patch 当前模块.now，import clock 才 patch clock.now

2. patch 保存原值、退出自动还原；patch.dict 可临时替换 os.environ

3. 时间/随机/网络优先依赖注入：FakeClock、random.Random(seed)、FakeHTTP，避免全局修改

[下一讲：属性测试、基准测试与模糊测试](/engineering/property-testing)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/076-mock.py`

```bash
python3 examples/lessons/076-mock.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/076-mock.py) · [全部示例代码索引](/examples/)
