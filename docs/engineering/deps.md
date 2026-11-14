---
title: 第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建
description: 让任意机器构建出相同的环境
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='40 分钟' goal='让任意机器构建出相同的环境' prereq='第 071 讲 · 项目结构与 src 布局' />

# 第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建

目录立稳之后，下一个常被跳过的问题是：换台机器、隔半年，还能装出同一组东西吗。一个服务预发跑得好好的，某天上游发了个小版本，生产装到新依赖后行为悄悄变了，回滚都找不出改了什么——所谓可复现，只是那天碰巧装到同一批包。

由声明走到锁定：先用 `pyproject.toml` 写清直接与传递依赖，再谈约束文件、锁文件与哈希校验，接着比 uv、poetry、pip-tools 的做法，最后补上供应链审计。前置是虚拟环境、pip 与模块概念；学完能把开发与运行依赖分开、提交锁文件，让任意机器构建出字节一致的环境。


## 上游发了个小版本，生产行为悄悄变了，回滚找不到改了什么

一个服务在预发跑得好好的，某天上游发布了一个小版本，生产环境按 `requirements.txt` 装到了新依赖，行为悄悄变了，回滚都找不到改了什么。

团队只写了 `requests>=2.28` 这样的宽泛范围，既没有锁文件也没有哈希，所谓「可复现」只是同一天碰巧装到同一组包。另一个更隐蔽的问题：开发依赖（pytest、mypy）和运行依赖混在一张清单里，生产镜像白胖一圈还带来额外攻击面。依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；

这要求把直接与传递依赖全部钉死到精确版本并校验哈希，区分开发与运行依赖，CI 用 `--require-hashes` 构建，定期审计已知漏洞。

本讲把 PEP 440/508、锁文件与供应链校验讲到能落地。

<Callout type="warn" title='先看一个真实会出错的写法' text='只写 requests&gt;=2.28 不提交锁文件：传递依赖解析随时间变化，某天上游发版就让线上行为悄悄改变' />


## pyproject.toml 里声明了什么：直接与传递依赖

PEP 621 把项目元数据集中到 `pyproject.toml` 的 `[project]`：name、version、requires-python、dependencies，`[project.optional-dependencies]` 放 dev/test 组；

PEP 518 的 `[build-system]` 声明 requires 与 build-backend（如 `setuptools.build_meta`）。

直接依赖是你显式声明的，传递依赖是它们的依赖，`pip freeze` 会把两者连同精确版本全部列出，这正是宽泛范围无法复现的原因：某天传递依赖发新版，解析结果就变。

版本规约遵循 PEP 440：`==2.32.3` 精确钉死，`~=1.4.5` 等价 `>=1.4.5, ==1.4.*`（兼容发布），`!=` 排除，`===` 任意相等，`1.2rc1` / `1.2.post1` / `1.2.dev1` / `+local` 分别表预发布、修订、开发、本地版本。

PEP 508 还统一了 extras 与环境标记：`uvicorn[standard]` 是带 extras 的写法，环境标记则是 `python_version >= '3.9'` 这类条件，或 `pytest; extra` 这种按 extra 生效的条目，可用 python_version、sys_platform、platform_machine 等变量。

```bash
pytest; extra == 'test'
```

<Callout type="tip" title='核心心智模型' text='PEP 621 把项目元数据集中到 `pyproject.toml` 的 `[project]`：name、version、requires-python、dependencies，`[project.optional-dependencies]` 放 dev/test 组；PEP 518 的…' />


## PEP 440 版本规约与 PEP 508 标记怎么读

**PEP 440 版本规约与 PEP 508 标记**

| 写法 | 含义 | 典型用途 |
| --- | --- | --- |
| ==2.32.3 | 精确版本 | 锁文件里钉死字节 |
| ~=1.4.5 | 等价 >=1.4.5, ==1.4.* | 允许补丁级升级 |
| >=2.28,<3 | 有界范围 | 运行依赖的宽松约束 |
| !=2.31.0 | 排除已知坏版本 | 绕过有 CVE 的发行 |
| ===foo | 任意相等（不走版本排序） | 非标准版本串 |
| 1.2rc1 / 1.2.post1 / 1.2.dev1 | 预发布 / 修订 / 开发版 | 发布流水线区分阶段 |
| pkg; python_version >= '3.9' | PEP 508 环境标记 | 按解释器版本条件生效 |
| uvicorn[standard] | extra 可选依赖 | 按需安装附加组 |

<Term word='pyproject.toml 规范' text='PEP 621 把项目元数据集中到 `pyproject.toml` 的 `[project]`：name、version、requires-python、dependencies，`[project.optional-dependencies]` 放 dev/test 组；PEP 518 的…' />

<Term word='直接与传递依赖' text='锁文件把一次成功解析的完整结果固化：`uv.lock`、`poetry.lock`、pip-tools 的 `requirements.txt`（由 `pip-compile` 从 `requirements.in` 生成），每行是 name==version 加一条 `--hash=sha256` 摘要。用…' />


### 兼容发布 ~= 与 >= 的边界差在哪

```python
import sys, os, tempfile
import importlib.metadata as im
import importlib

def make_dist(root, name, version, requires_lines):
    di = os.path.join(root, name + '-' + version + '.dist-info')
    os.makedirs(di)
    lines = ['Metadata-Version: 2.1', 'Name: ' + name, 'Version: ' + version]
    lines += ['Requires-Dist: ' + r for r in requires_lines]
    open(os.path.join(di, 'METADATA'), 'w').write(chr(10).join(lines) + chr(10))

importlib.invalidate_caches()
with tempfile.TemporaryDirectory() as d:
    make_dist(d, 'app', '1.0', ['lib>=2.0'])
    make_dist(d, 'lib', '1.5', [])
    sys.path.insert(0, d)
    versions = {n: im.version(n) for n in ('app', 'lib')}
    print('installed', versions)
    need = 2
    have = int(versions['lib'].split('.')[0])
    print('conflict detected', have < need)
    sys.path.remove(d)
```

<OutputBox title='原理验证' output='installed {&#39;app&#39;: &#39;1.0&#39;, &#39;lib&#39;: &#39;1.5&#39;}\nconflict detected True' />


## 对照：requirements.txt 宽泛范围与锁文件

```python
import hashlib

def digest(body):
    return hashlib.sha256(body.encode()).hexdigest()

lock = [
    ('requests', '2.32.3', digest('requests-2.32.3')),
    ('certifi', '2024.8.30', digest('certifi-2024.8.30')),
]

def verify(pkg, payload):
    return digest(payload) == pkg[2]

print('pinned', [v for _, v, _ in lock])
print('hash bits', len(lock[0][2]) * 4)
print('exact match ok', verify(lock[0], 'requests-2.32.3'))
print('tampered rejected', not verify(lock[0], 'requests-2.32.3-tampered'))
print('unpinned upgrade rejected', not verify(lock[0], 'requests-2.33.0'))
```

<OutputBox title='主示例运行结果' output='pinned [&#39;2.32.3&#39;, &#39;2024.8.30&#39;]\nhash bits 256\nexact match ok True\ntampered rejected True\nunpinned upgrade rejected True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib\n\ndef digest(body):\n    return hashlib.sha256(body.encode()).hexdigest()\n\nlock = [\n    (&#39;requests&#39;, &#39;2.32.3&#39;, digest(&#39;requests-2.32.3&#39;)),\n    (&#39;certifi&#39;, &#39;2024.8.30&#39;, digest(&#39;certifi-2024.8.30&#39;)),\n]\n\ndef verify(pkg, payload):\n    return digest(payload) == pkg[2]\n\nprint(&#39;pinned&#39;, [v for _, v, _ in lock])\nprint(&#39;hash bits&#39;, len(lock[0][2]) * 4)\nprint(&#39;exact match ok&#39;, verify(lock[0], &#39;requests-2.32.3&#39;))\nprint(&#39;tampered rejected&#39;, not verify(lock[0], &#39;requests-2.32.3-tampered&#39;))\nprint(&#39;unpinned upgrade rejected&#39;, not verify(lock[0], &#39;requests-2.33.0&#39;))' :notes='["导入 hashlib 做 SHA-256 摘要，模拟锁文件的哈希校验", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 digest：对精确版本字节串算 256 位十六进制摘要", "返回十六进制摘要字符串，长度 64 字符", "空行，只用于分隔逻辑块，不影响执行结果。", "lock 模拟锁文件：每项为 (包名, 精确版本, sha256)", "requests 钉在 2.32.3 并记录其摘要", "certifi 钉在 2024.8.30 并记录其摘要", "verify 比对下载件摘要与锁定摘要是否一致", "空行，只用于分隔逻辑块，不影响执行结果。", "一致才允许安装，否则拒绝", "打印被钉死的精确版本，不含任何范围", "空行，只用于分隔逻辑块，不影响执行结果。", "十六进制每位 4 bit，64 字符即 256 位", "字节完全相同的产物校验通过", "被篡改的产物摘要不同，校验失败被拒", "上游发新版也会因摘要不符被拒，复现性得以保证", "PEP 621 [project] + PEP 518 [build-system]；PEP 440 管版本，PEP 508 管 extras 与环境标记"]' title='第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import sys, os, tempfile
import importlib.metadata as im
import importlib
importlib.invalidate_caches()

with tempfile.TemporaryDirectory() as d:
    di = os.path.join(d, 'demo_pkg-1.2.3.dist-info')
    os.makedirs(di)
    with open(os.path.join(di, 'METADATA'), 'w') as f:
        f.write('Metadata-Version: 2.1' + chr(10) + 'Name: demo-pkg' + chr(10)
                + 'Version: 1.2.3' + chr(10) + 'Requires-Python: >=3.9' + chr(10)
                + 'Requires-Dist: requests>=2.28' + chr(10))
    sys.path.insert(0, d)
    dist = im.distribution('demo-pkg')
    print('name', dist.metadata['Name'])
    print('version', dist.version)
    print('requires-python', dist.metadata['Requires-Python'])
    print('requires', dist.requires)
    sys.path.remove(d)
```

<OutputBox title='对照写法：先自己猜，再点开' output='name demo-pkg\nversion 1.2.3\nrequires-python &gt;=3.9\nrequires [&#39;requests&gt;=2.28&#39;]' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import hashlib\n\ndef digest(body):\n    return hashlib.sha256(body.encode()).hexdigest()\n\nlock = [\n    (&#39;requests&#39;, &#39;2.32.3&#39;, digest(&#39;requests-2.32.3&#39;)),\n    (&#39;certifi&#39;, &#39;2024.8.30&#39;, digest(&#39;certifi-2024.8.30&#39;)),\n]\n\ndef verify(pkg, payload):\n    return digest(payload) == pkg[2]\n\nprint(&#39;pinned&#39;, [v for _, v, _ in lock])\nprint(&#39;hash bits&#39;, len(lock[0][2]) * 4)\nprint(&#39;exact match ok&#39;, verify(lock[0], &#39;requests-2.32.3&#39;))\nprint(&#39;tampered rejected&#39;, not verify(lock[0], &#39;requests-2.32.3-tampered&#39;))\nprint(&#39;unpinned upgrade rejected&#39;, not verify(lock[0], &#39;requests-2.33.0&#39;))", "note": "pyproject.toml、直接与传递依赖、版本规约"}, {"label": "对照 / 进阶", "code": "import sys, os, tempfile\nimport importlib.metadata as im\nimport importlib\nimportlib.invalidate_caches()\n\nwith tempfile.TemporaryDirectory() as d:\n    di = os.path.join(d, &#39;demo_pkg-1.2.3.dist-info&#39;)\n    os.makedirs(di)\n    with open(os.path.join(di, &#39;METADATA&#39;), &#39;w&#39;) as f:\n        f.write(&#39;Metadata-Version: 2.1&#39; + chr(10) + &#39;Name: demo-pkg&#39; + chr(10)\n                + &#39;Version: 1.2.3&#39; + chr(10) + &#39;Requires-Python: &gt;=3.9&#39; + chr(10)\n                + &#39;Requires-Dist: requests&gt;=2.28&#39; + chr(10))\n    sys.path.insert(0, d)\n    dist = im.distribution(&#39;demo-pkg&#39;)\n    print(&#39;name&#39;, dist.metadata[&#39;Name&#39;])\n    print(&#39;version&#39;, dist.version)\n    print(&#39;requires-python&#39;, dist.metadata[&#39;Requires-Python&#39;])\n    print(&#39;requires&#39;, dist.requires)\n    sys.path.remove(d)", "note": "锁文件、约束与哈希校验"}]' title='两种写法对照' note='差异集中在 pyproject.toml 规范；先看输出，再找背后的规则。' />

**宽泛范围 vs 锁文件的复现性**

| 维度 | requirements.txt 写 >=2.28 | 锁文件 + --require-hashes |
| --- | --- | --- |
| 传递依赖 | 每次解析可能不同 | 全部钉死到精确版本 |
| 上游发新版 | 静默装到新版本 | 哈希不符直接报错 |
| 下载件被篡改 | 不校验，照装 | sha256 不符拒绝安装 |
| 跨机器构建 | 依赖当天索引状态 | 任意时间同一组字节 |
| 开发/运行依赖 | 常混在一张表 | 分组或分文件，生产只装运行组 |


## 锁文件、约束文件与 --require-hashes

锁文件把一次成功解析的完整结果固化：`uv.lock`、`poetry.lock`、pip-tools 的 `requirements.txt`（由 `pip-compile` 从 `requirements.in` 生成），每行是 name==version 加一条 `--hash=sha256` 摘要。

用 `--require-hashes` 安装时，pip 会对每个下载件校验哈希，任何篡改、上游重传、未锁定的新版本都会被拒绝；

缺哈希或版本不匹配直接报错，而不是装上一个「差不多」的包。

要注意普通 `pip install` 不会主动校验哈希，这份保证来自锁文件里的哈希加上 `--require-hashes` 模式。

区分两层：约束文件（`constraints.txt`）只限制版本不选包，锁文件同时选定包与版本。

开发依赖与运行依赖要拆成不同组或不同文件，生产镜像只装运行组。

用 `importlib.metadata` 读取已安装分发的 `METADATA`，可核对 Name、Version、Requires-Python、Requires-Dist；

用两个假分发模拟 app 要求 `lib>=2.0` 却装了 1.5，就能复现 `pip check` 要报的依赖冲突。

**依赖管理工具与产物**

| 工具 / 文件 | 产物 | 关键命令 / 字段 |
| --- | --- | --- |
| python -m venv .venv | 隔离环境 + pyvenv.cfg | 激活后 site-packages 独立 |
| uv | uv.lock | uv lock / uv sync --frozen |
| poetry | poetry.lock | poetry install --sync |
| pip-tools | requirements.txt（带哈希） | pip-compile --generate-hashes |
| pip | 已装分发 | pip install --require-hashes -r req.txt |
| pip check | 冲突报告 | 校验 Requires-Dist 与已装版本是否自洽 |
| importlib.metadata | 读取 METADATA | version / requires / metadata['Requires-Python'] |

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `pyproject.toml` 规范 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## pip 解析依赖：Requirement 对象与 Version 偏序

pip 解析依赖时把每个发行版的 `METADATA` 读成 Requirement 对象（PEP 508），用 PEP 440 的 `Version` 类做偏序比较，在候选版本集合里做回溯搜索满足所有约束的组合；宽泛范围下这个搜索结果会随时间（索引新增版本）变化，这就是不可复现的根源。

锁文件把搜索结果连同每个 wheel/sdist 的 sha256 一起固化，`--require-hashes` 模式要求每个待装件都带哈希且必须匹配，否则在下载完成后、安装前拒绝，从机制上同时挡住「解析漂移」与「字节篡改」。

`importlib.metadata` 通过 `sys.path` 上的 `*.dist-info/METADATA`（RFC 822 风格头）读取 Name、Version、Requires-Python、Requires-Dist，`pip check` 正是比对 Requires-Dist 与已装版本是否满足约束。

SHA-256 把任意长度输入映射为 256 位摘要，输入改变一位输出约半数比特翻转，因此精确版本加摘要可作为「同一组字节」的可验证判据。

<ConceptDiagram type='layers3' title='第 072 讲 · pyproject.toml、直接与传递依赖、版本规约' labels='pyproject.toml、直接与传递依赖…|锁文件、约束与哈希校验|可复现构建与供应链安全|供应链安全' caption='让任意机器构建出相同的环境' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 可复现构建与供应链安全

CI 的最低要求：提交锁文件、用标准库或 uv 各建一个干净虚拟环境、按锁文件加 `--require-hashes` 安装、跑 `pip check` 验证已装依赖自洽、把解释器版本写进镜像标签。

哈希校验防的是「字节被换」：`hashlib.sha256` 对精确版本产物算 256 位摘要，任何一位变化都会让摘要不同；钉死版本挡住「上游悄悄发版」，哈希挡住「下载件被篡改」，两者分工不同却常被混为一谈。

供应链还要加 `--only-binary=:all:` 避免安装时执行任意构建脚本、定期用 pip-audit / uv 审计已知 CVE、把依赖升级做成有评审的 PR 而不是随手 bump。

生产密钥与配置不进依赖清单；依赖镜像用可信源并固定 index-url。

判断环境是否可复现有个可测标准：删掉虚拟环境按锁文件从零装，跑出的 `importlib.metadata.version()` 集合与锁定值逐项一致，且 `pip check` 无输出。

<FlowTimeline :steps='[{"title": "pyproject.toml、直接与传递依赖、版…", "desc": "PEP 621 把项目元数据集中到 `pyproject.toml` 的…", "tone": "blue"}, {"title": "锁文件、约束与哈希校验", "desc": "锁文件把一次成功解析的完整结果固化：`uv.lock`、`poetry.lock`…", "tone": "purple"}, {"title": "可复现构建与供应链安全", "desc": "CI 的最低要求：提交锁文件、用标准库或 uv 各建一个干净虚拟环境、按锁文件加…", "tone": "orange"}, {"title": "工程落地", "desc": "可复现构建清单：哈希校验与冲突自检", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 可复现构建清单：哈希校验与冲突自检

发布流水线里，依赖环节应当是一条会自己失败的闸门：从锁文件读出每个包的精确版本与 sha256，下载件先过哈希才允许安装，装完再跑 `pip check` 式的冲突自检，最后打印可审计的 manifest。把这一步写成脚本随代码提交，就能在任何机器上重建同一组字节。

下面片段用标准库模拟三件带哈希的锁定包，构造安装 manifest，并故意替换其中一个产物验证拒绝路径；真实项目把 install 换成 pip/uv 调用、把 digest 换成读取锁文件即可。

```python
import hashlib, json

def sha(body):
    return hashlib.sha256(body.encode()).hexdigest()

LOCK = [
    ('httpx', '0.27.0', sha('httpx-0.27.0')),
    ('certifi', '2024.7.4', sha('certifi-2024.7.4')),
    ('idna', '3.7', sha('idna-3.7')),
]

def install(pkg, payload):
    name, version, expected = pkg
    if sha(payload) != expected:
        raise ValueError('hash mismatch for ' + name)
    return name + '==' + version

def build_manifest(lock, artifacts):
    pinned = [install(pkg, payload) for pkg, payload in zip(lock, artifacts)]
    return {'python': '3.13', 'packages': pinned, 'hashes': True}

artifacts = ['httpx-0.27.0', 'certifi-2024.7.4', 'idna-3.7']
print(json.dumps(build_manifest(LOCK, artifacts), sort_keys=True))
try:
    build_manifest(LOCK, ['httpx-0.27.0-evil', 'certifi-2024.7.4', 'idna-3.7'])
except ValueError as e:
    print('rejected', str(e))
```

<Callout type="idea" title='落地提示' text='提交锁文件、区分开发与运行依赖、CI 用 --require-hashes，并定期审计已知漏洞' />

<CheckList id='P072b' title='上线前自检' :items='["能复现并解释「只写 requests&gt;=2.28 不提交锁文件」", "能复现并解释「开发与运行依赖混在一张清单」", "能复现并解释「锁了版本却不校验哈希」", "能用一条命令验证 pyproject.toml 规范", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只写 requests>=2.28 不提交锁文件 | 传递依赖解析随时间变化，某天上游发版就让线上行为悄悄改变 | 提交 uv.lock / poetry.lock / pip-compile 生成的带哈希 requirements.txt，CI 用 --require-hashes 安装 |
| 开发与运行依赖混在一张清单 | 生产镜像装上 pytest/mypy，体积膨胀且扩大攻击面 | 用 [project.optional-dependencies] 或 PEP 735 dependency-groups 分组，生产只装运行依赖 |
| 锁了版本却不校验哈希 | 能挡住发版漂移，挡不住下载件被替换或上游重传 | 锁文件每行带 --hash=sha256:...，安装启用 --require-hashes，并用 pip-audit 定期审计 CVE |

<Callout type="warn" title='本讲最容易踩的坑' text='只写 requests&gt;=2.28 不提交锁文件：传递依赖解析随时间变化，某天上游发版就让线上行为悄悄改变' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只写 requests&gt;=2.28 不提交锁…", "body": "传递依赖解析随时间变化，某天上游发版就让线上行为悄悄改变", "tip": "提交 uv.lock / poetry.lock / pip-compile 生成的带哈希 requirements.txt，CI 用 --require-hashes 安装"}, {"title": "第 2 步：开发与运行依赖混在一张清单", "body": "生产镜像装上 pytest/mypy，体积膨胀且扩大攻击面", "tip": "用 [project.optional-dependencies] 或 PEP 735 dependency-groups 分组，生产只装运行依赖"}, {"title": "第 3 步：锁了版本却不校验哈希", "body": "能挡住发版漂移，挡不住下载件被替换或上游重传", "tip": "锁文件每行带 --hash=sha256:...，安装启用 --require-hashes，并用 pip-audit 定期审计 CVE"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：验证 SHA-256 的固定长度与篡改敏感性' task='对精确版本串算 sha256，打印十六进制长度，并证明在串尾追加字符后摘要不同。' solution='import hashlib\nh = hashlib.sha256(b&#39;lib-1.0&#39;).hexdigest()\nprint(&#39;hex length&#39;, len(h), &#39;bits&#39;, len(h) * 4)\nprint(&#39;tampered differs&#39;, hashlib.sha256(b&#39;lib-1.0-x&#39;).hexdigest() != h)' explain='sha256 输出 64 个十六进制字符即 256 位；输入变一位输出约半数比特翻转，所以摘要可作「同一组字节」的判据，锁文件据此拒绝被换的产物。' />

<Exercise title='进阶：解析钉死版本行与环境标记' task='把 name==version 拆出包名与版本，再识别一行是否带 PEP 508 环境标记，打印结果。' solution='line = &#39;requests==2.32.3&#39;\nname, version = line.split(&#39;==&#39;)\nprint(&#39;name&#39;, name, &#39;parts&#39;, len(version.split(&#39;.&#39;)))\nmarked = &#39;uvicorn[standard]==0.30.1; python_version &gt;= "3.9"&#39;\nprint(&#39;has marker&#39;, &#39;;&#39; in marked, &#39;has extra&#39;, &#39;[&#39; in marked)' explain='== 钉死精确版本，split(&#39;==&#39;) 可拆出包与版本；分号后是 PEP 508 环境标记，方括号是 extra 可选依赖，二者让同一份声明按环境与用途条件生效。' />

<Quiz no='072-1' q='只写 requests&gt;=2.28 且不提交锁文件，主要风险是？' :options='["传递依赖会随时间重新解析，某天上游发版就改变线上行为", "pip 无法安装 requests", "requests 不再兼容 Python 3", "哈希校验总是失败"]' answer="0" explain='宽泛范围下 pip 每次按当前索引求解传递依赖，结果不确定；锁文件把全部直接与传递依赖钉到精确版本，才能保证任意时间同一组字节。' />

<Quiz no='072-2' q='--require-hashes 的作用是？' :options='["安装前校验每个下载件的 sha256 与锁文件一致，不符即拒绝", "自动生成 requirements.txt", "跳过传递依赖解析", "把依赖编译成 wheel"]' answer="0" explain='该模式要求每个待装件带哈希且必须匹配，既挡住上游重传/篡改，也挡住未锁定的新版本被装上，是供应链校验的关键一环。' />

<Quiz no='072-3' q='~=1.4.5 这个 PEP 440 兼容发布规约等价于？' :options='["&gt;=1.4.5, ==1.4.*", "==1.4.5", "&gt;=1.4.5,&lt;2.0", "任意 1.x 版本"]' answer="0" explain='~=1.4.5 允许最后一段之后的补丁级升级，等价 &gt;=1.4.5 且 ==1.4.*；它与 ~=1.4（等价 &gt;=1.4, ==1.*）只因保留位数不同而范围不同。' />

<Predict no='072-4' q='对锁定为 requests==2.32.3 的包，用下载件 requests-2.33.0 校验哈希，会被拒绝吗？' :options='["会，摘要不符被拒绝", "不会，版本相近就放行", "会，但只警告不阻断"]' answer='0' output='会，摘要不符被拒绝' explain='锁文件把版本与 sha256 绑定，2.33.0 的字节串与锁定值不同，摘要必然不同；--require-hashes 模式下这一步直接报错拒绝安装，从而挡住未锁定的升级。' />

<FillBlank no='072-5' tpl='___ hashlib' :answers='["import"]' hint='回想本讲关于 pyproject.toml 规范 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 pyproject.toml、直接与传递依赖、版本规约 的落点。' />

<KnowledgeCard :points='["依赖管理目标是在任意时间、任意机器装出同一组字节，而非「能装上」", "PEP 621 [project] + PEP 518 [build-system]；PEP 440 管版本，PEP 508 管 extras 与环境标记", "~=1.4.5 等价 &gt;=1.4.5, ==1.4.*；== 精确钉死，锁文件全部用精确版本", "uv.lock / poetry.lock / pip-compile 产物要提交；CI 用 --require-hashes 安装并跑 pip check", "uvicorn[standard] 是 extras 不是环境标记；哈希由锁文件提供、靠 --require-hashes 才会校验", "sha256 为 256 位摘要；开发/运行依赖分组，生产只装运行组并定期审计 CVE"]' :pitfalls='["只写 requests&gt;=2.28 不提交锁文件", "开发与运行依赖混在一张清单", "锁了版本却不校验哈希", "开发与生产共用一份无锁依赖，某天上游发版就会让线上行为悄悄变化"]' summary='依赖管理的目标不是「装上」，而是「在任何时间、任何机器上装出同一组字节」；只写 requirements.txt 的宽泛范围做不到这点' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 依赖管理目标是在任意时间、任意机器装出同一组字节，而非「能装上」 | 建立直觉 |
| PEP 621 [project] + PEP 518 [build-system]；PEP 440 管版本，PEP 508 管 extras 与环境标记 | 跑通示例 |
| ~=1.4.5 等价 >=1.4.5, ==1.4.*；== 精确钉死，锁文件全部用精确版本 | 深入边界 |
| uv.lock / poetry.lock / pip-compile 产物要提交；CI 用 --require-hashes 安装并跑 pip check | 工程落地 |
| uvicorn[standard] 是 extras 不是环境标记；哈希由锁文件提供、靠 --require-hashes 才会校验 | 随堂检测 |
| sha256 为 256 位摘要；开发/运行依赖分组，生产只装运行组并定期审计 CVE | 复盘 |

1. 依赖管理目标是在任意时间、任意机器装出同一组字节，而非「能装上」

2. PEP 621 [project] + PEP 518 [build-system]；PEP 440 管版本，PEP 508 管 extras 与环境标记

3. ~=1.4.5 等价 >=1.4.5, ==1.4.*；== 精确钉死，锁文件全部用精确版本

[下一讲：代码规范：PEP 8、ruff、black 与 pre-commit](/engineering/style)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/072-deps.py`

```bash
python3 examples/lessons/072-deps.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/072-deps.py) · [全部示例代码索引](/examples/)
