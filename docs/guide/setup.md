---
title: 第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器
description: 搭好可复现、可隔离、可协作的开发环境
---

<StageHeader stage='L0 · 导学' level='★☆☆☆☆' time='30 分钟' goal='搭好可复现、可隔离、可协作的开发环境' prereq='第 001 讲 · 开篇：Python 是什么，为什么值得学' />

# 第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器

上一讲说清了 Python 能做什么，你多半已装好解释器，正想动手。先把落脚处安顿好：代码由哪个解释器跑、第三方包装在哪、换台机器结果是否一样——这些决定了往后每次运行是否踏实。想想协作时同一份代码，你本地正常、对方却差一截，或两个项目的依赖互相打架；毛病多半不在代码，而在环境没对齐。我们先认解释器版本与实现，再看 venv 怎样给每个项目划出独立依赖空间，最后把版本和依赖写进 `pyproject.toml` 与锁文件，做到一行复原。会打开终端、按第 1 讲敲几条命令就够；学完你能搭出可复现、可隔离的开发环境，不再为『在我这儿是好的』折腾。


## 新同事 clone 仓库后，第一行就报 ModuleNotFoundError

周一早上，新同事 clone 完数据服务仓库，照着 `README` 里的说明运行 `main.py`，第一行就报 ModuleNotFoundError，找不到 requests。他按报错装 requests，接着报 pandas 版本冲突；

换成同事发来的 `requirements.txt` 全量安装，服务能起来了，本地跑出的报表数字却和测试环境差了一截——因为那份文件里 pandas 只写了 `>=1.5`，两人分别装到 1.5 与 2.2，而 2.x 改过 groupby 的默认行为。

朴素解法是「缺什么装什么、版本装最新的」，它失败在三个变量从未被对齐：解释器版本（他机器是 3.13，CI 是 3.11）、依赖的精确集合（只有下界没有锁）、以及工作目录与 site-packages 的归属（全局安装让两个项目共用同一份包）。任何一项漂移，都足以让「在我机器上是好的」变成线上事故。

本讲把这三个变量变成能读、能写进配置文件、能一行复原的具体量。


## 解释器身份：sys 里能读到的四个字段

`sys.version_info` 是 5 元素具名元组 (major, minor, micro, releaselevel, serial)，官方推荐用 `sys.version_info >= (3, 8)` 做门槛判断，因为元组按数值逐位比较；

绝不能拿 `sys.version` 那个字符串去比『3.10』是否小于『3.9』，字典序会把 3.10 判成比 3.9 小。`sys.hexversion` 把版本编成一个整数，适合 C 扩展做数值比较。`sys.executable` 给出当前解释器二进制的绝对路径，是判断「我到底在用哪个 python」的唯一可靠依据。

`sys.implementation.name` 返回 cpython、pypy 这类实现名，与语言版本分开：同一份 3.11 语法在 CPython 与 PyPy 上跑，version_info 相同而 implementation 不同。

`sys.prefix` 与 `sys.base_prefix` 是判定虚拟环境的关键，标准解释器里二者相等，进入 venv 后 `sys.prefix` 指向 venv 目录、`sys.base_prefix` 仍指向系统前缀（PEP 405，3.3 起）。

版本管理工具 pyenv 靠在 `PATH` 前插入 shim 切换 python 指向，uv 则把各版本装进独立目录、用 `.python-version` 固定当前选择，两者改的都是「用哪个解释器」，不会动项目依赖。

3.13 起还能用 `sys._is_gil_enabled()` 判断当前构建是否为自由线程版，这会改变并发相关的结论。

```python
import os, sys, site

report = {
    'version': '%d.%d.%d' % sys.version_info[:3],
    'executable': sys.executable,
    'in_venv': sys.prefix != sys.base_prefix,
    'cwd': os.getcwd(),
    'site_count': len(site.getsitepackages()),
}

print('keys', sorted(report))
print('in_venv', report['in_venv'])
print('version_major', sys.version_info[0])
print('site_ok', report['site_count'] >= 1)
print('cwd_abs', os.path.isabs(report['cwd']))
```

<OutputBox title='主示例运行结果' output='keys [&#39;cwd&#39;, &#39;executable&#39;, &#39;in_venv&#39;, &#39;site_count&#39;, &#39;version&#39;]\nin_venv False\nversion_major 3\nsite_ok True\ncwd_abs True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import os, sys, site\n\nreport = {\n    &#39;version&#39;: &#39;%d.%d.%d&#39; % sys.version_info[:3],\n    &#39;executable&#39;: sys.executable,\n    &#39;in_venv&#39;: sys.prefix != sys.base_prefix,\n    &#39;cwd&#39;: os.getcwd(),\n    &#39;site_count&#39;: len(site.getsitepackages()),\n}\n\nprint(&#39;keys&#39;, sorted(report))\nprint(&#39;in_venv&#39;, report[&#39;in_venv&#39;])\nprint(&#39;version_major&#39;, sys.version_info[0])\nprint(&#39;site_ok&#39;, report[&#39;site_count&#39;] &gt;= 1)\nprint(&#39;cwd_abs&#39;, os.path.isabs(report[&#39;cwd&#39;]))' :notes='["导入 os 读工作目录、sys 读解释器状态、site 读站点目录", "report 把环境三要素收进一个字典，便于整体打印与比对", "version_info[:3] 取前三段格式化成 major.minor.micro", "sys.executable 是当前解释器二进制的绝对路径", "sys.prefix != sys.base_prefix 是 PEP 405 定义的 venv 判据", "os.getcwd() 记录工作目录，它决定 sys.path[0] 的一部分", "site.getsitepackages() 返回生效的站点目录，数量至少为一", "字典闭合；此时 report 只是内存里的普通 dict", "打印排序后的键，验证三要素都已被采集", "未激活 venv 时 prefix 与 base_prefix 相等，输出 False", "version_info[0] 是 major，单独打印便于做版本门槛", "站点目录数量 &gt;= 1 说明依赖有安装位置", "cwd 是绝对路径，说明工作目录这一变量已可核对"]' title='第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 依赖集合：venv 靠 sys.prefix 切换 site-packages

建好虚拟环境后，目录里会生成 `pyvenv.cfg`、bin 下的 python 副本，以及 lib/python3.13/site-packages 这样的站点目录。激活脚本做的事比想象中少：它主要把 .venv/bin 插到 `PATH` 最前面，让敲 python 时命中虚拟环境里的副本；

真正决定包装到哪、从哪里读的，是解释器启动时读 `pyvenv.cfg` 里的 home，把 `sys.prefix` 改成 .venv，site 模块据此把 .venv/lib/python3.13/site-packages 加进 `sys.path`，而标准库仍从 `sys.base_prefix` 加载。

所以「venv 里装的包，系统 python 读不到」不是玄学，是两条不同的 `sys.path`。

`site.getsitepackages()` 返回当前生效的站点目录列表，`site.ENABLE_USER_SITE` 控制是否叠加用户级目录。

装包务必用 `python -m` 而不是裸 `pip install`：`PATH` 上那个 pip 脚本可能属于另一个解释器，会把包写进错误的 site-packages，而 -m pip 保证 pip 模块由当前 `sys.executable` 加载。

```bash
python -m pip install
```

国内镜像（pip 的 `-i` 参数、`PIP_INDEX_URL` 环境变量、`pip.conf` 的 index-url）只替换下载源，不改变依赖解析出的版本号，版本仍由约束文件决定。

还有两个版本细节：3.3 起 venv 自带 ensurepip，但 3.12 起 venv 默认不再预装 setuptools，老教程里「进 venv 直接跑 `setup.py`」的前提已经不成立了。

**解释器身份字段对照**

| 字段 | 类型与示例 | 用途 |
| --- | --- | --- |
| sys.version_info | 5 元素具名元组 (3, 13, 12, 'final', 0) | 数值门槛判断 >= (3, 8) |
| sys.hexversion | 整数，如 3.13.12 对应 0x030D0CF0 | C 扩展做数值版本比较 |
| sys.executable | 绝对路径字符串 | 确认当前用的是哪个 python |
| sys.implementation.name | cpython 或 pypy | 区分实现而非语言版本 |
| sys.prefix / sys.base_prefix | 两个路径字符串 | 不等即处于 venv |
| sys._is_gil_enabled() | bool（3.13 起） | 判断是否自由线程构建 |


### 激活前后的路径变量对照

(venv) 提示符不代表解释器换了，activate 只把 .venv/bin 顶到 `PATH` 最前。判断生效别只信 which python——bash 的 hash 缓存留旧路径，得先 hash -r；

更稳的是 `python -c` 打印 `sys.executable` 看是否指向 .venv，并看 `sys.prefix` 与 `sys.base_prefix` 是否分家。

用绝对路径 /usr/bin/python 会绕开它。下表把 `PATH`、`sys.executable`、`sys.prefix` 激活前后对照。

**venv 激活前后的路径变量**

| 变量 | 系统解释器 | venv 内 | 后果 |
| --- | --- | --- | --- |
| sys.prefix | 系统前缀 | .venv 目录 | site-packages 从它推导 |
| sys.base_prefix | 系统前缀 | 仍为系统前缀 | 标准库始终从这里加载 |
| sys.path 里的站点目录 | 系统 site-packages | .venv/lib/python3.13/site-packages | 两处包互不可见 |
| sys.executable | 系统 python | .venv/bin/python | 决定 -m pip 装到哪 |


## 工作目录与复现：pyproject.toml、锁文件与隔离模式

复现要同时钉住三样东西，缺一个就会漂移。

`pyproject.toml` 的 `[project].dependencies` 只声明直接依赖的抽象约束（如 `requests>=2.31` 或兼容写法 `~=2.31.0`），它表达的是「能接受什么范围」，不是「最终装了什么」。

锁文件（`uv.lock`、`poetry.lock`，或 `pip freeze` 导出的带 `==` 与 `--hash` 的 `requirements.lock`）把整棵依赖树——含间接依赖——固定到精确版本与 sha256 摘要；

CI 按锁文件原样安装、不重新解析，例如 `uv sync` 或带 `--require-hashes` 的 `pip install`，也就不接受被替换的包。

```bash
uv sync --frozen
```

工作目录则通过 `sys.path[0]` 影响导入：用 `python -m` 时，`python -m pkg.mod` 把当前工作目录放进搜索路径、以模块方式执行（`__package__` 正确，包内相对导入可用），而按脚本路径直接运行时，解释器只把脚本所在目录放进路径、不建立包上下文，此时 `from . import helper` 会报 ImportError，提示没有已知的父包。

`python -I`（3.4 起）进入隔离模式：忽略所有 `PYTHON*` 环境变量、移除脚本目录与用户站点，让 CI 和本地看到同一套路径；配套的 `-E` 忽略环境变量、`-s` 禁用用户站点、`-S` 干脆不导入 site。

最典型的失效信号是「本地能 import、CI 报 ModuleNotFoundError」：多半是当前目录被悄悄当成了包根，或某个包装在用户站点里而 CI 用 -I 跑。

把 `python -V`、打印 `sys.executable`、以及 `python -I` 写进同一个 Makefile 目标，三个变量才算对齐。

```bash
python -I -m pytest
```


## 从裸 pip 到 python -m：命令写法对照

```python
import sys
f = sys.flags
print('impl_name', sys.implementation.name)
print('version_len', len(sys.version_info) >= 5)
print('hexversion_positive', sys.hexversion > 0)
print('flags_optimize', f.optimize)
print('flags_isolated', bool(f.isolated))
print('flags_no_site', bool(f.no_site))
print('path_ordered', isinstance(sys.path, list))
```

<OutputBox title='对照写法：先自己猜，再点开' output='impl_name cpython\nversion_len True\nhexversion_positive True\nflags_optimize 0\nflags_isolated False\nflags_no_site False\npath_ordered True' guess="true" />


## CPython 启动阶段怎样拼出 sys.path

CPython 启动阶段按顺序拼出 `sys.path`，这个顺序决定了「谁被导入」。

解释器先由 `argv[0]` 定位可执行文件，检查同目录或上级的 `pyvenv.cfg`：若存在，读取其中的 home 作为 `sys.base_prefix`，把自身所在前缀设为 `sys.prefix`，这就是 venv 隔离的全部秘密。

随后 site 模块被自动导入，它调用 addsitedir 把 `sys.prefix` 下的 site-packages 追加到 `sys.path`，并处理其中的 `.pth` 文件（.pth 里以 import 开头的行还会被执行）。

最终 `sys.path` 的顺序是：脚本目录或空串（代表当前工作目录）、`PYTHONPATH`、标准库 zip 与目录、第三方 site-packages；import 沿这个列表从左到右找，先命中者赢，因此项目里一个与标准库同名的 `json.py` 就能遮蔽真正的 json 模块。

找到模块后，import 把新建的 module 对象写入 `sys.modules` 字典，键是完整模块名；

之后任何 import 都先查这个缓存直接复用，所以同一进程内依赖集合是固定的单例，改了磁盘上的 .py 文件不会自动生效，必须重启进程或 `importlib.reload`。

这也解释了为什么锁文件要带哈希：pip 的 `--require-hashes` 在下载后比对 sha256，正是为了防止镜像或缓存把包换成另一个字节序列。

<ConceptDiagram type='layers3' title='第 002 讲 · 解释器版本：sys 里能读到的四个字段' labels='解释器版本：sys 里能读到的四个字段|依赖集合：venv 靠 sys.prefix|工作目录与复现：pyproject.toml' caption='搭好可复现、可隔离、可协作的开发环境' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## CI 环境自检：把四个事实打成一份可核对的报告

CI 里最贵的故障不是代码写错，而是构建环境与本地不一致：runner 用的是 3.11、本地是 3.13；runner 没激活 venv 却把包装进了用户站点；或者锁文件被人手改过却没人发现。

与其在流水线里靠一串 shell 命令碰运气，不如让程序自己把四个事实打印成一份可贴进工单的报告：解释器是否达到版本门槛、当前是否处在虚拟环境、关键依赖能否被 find_spec 定位、以及锁文件内容哈希的长度是否符合预期。

下面这段不依赖任何第三方工具，只用一个标准库脚本完成自检：它用 `sys.version_info` 做数值门槛，用 `sys.prefix` 与 `sys.base_prefix` 判断隔离状态，用 `importlib.util.find_spec` 验证依赖可达，用 `hashlib.sha256` 把锁文件字节固化成摘要。

把 lock_bytes 换成 CI 里真实读到的文件、把期望摘要写进环境变量，就能在编译之前拦下大多数环境类故障。真实项目还应把这份报告接到日志系统，并让失败项以非零退出码结束进程。

```python
import sys, os, tempfile, hashlib, importlib.util

def env_checks(least, deps, lock_bytes):
    checks = {}
    checks['version'] = sys.version_info >= least
    checks['venv'] = sys.prefix != sys.base_prefix
    checks['deps'] = all(importlib.util.find_spec(m) is not None for m in deps)
    checks['lock_sha'] = hashlib.sha256(lock_bytes).hexdigest()[:12]
    return checks

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(b'requests==2.32.3' + bytes([10]))
    path = tmp.name
with open(path, 'rb') as f:
    blob = f.read()
os.unlink(path)

r = env_checks((3, 8), ['json', 'hashlib'], blob)
print('version_ok', r['version'])
print('deps_ok', r['deps'])
print('lock_sha_len', len(r['lock_sha']))
print('all_importable', r['deps'] and r['version'])
```

<Callout type="idea" title='落地提示' text='工程上用 pyproject.toml 声明依赖、用锁文件固定版本、CI 用同一份锁文件构建，是环境可复现的最低要求' />


## 换台机器能否一行复原：错因速查

一行复原指 uv sync --frozen 这类按锁文件装、不重新解析的命令，而非照 `requirements.txt` 重装。

失灵时依次查：先 `python -V` 对齐解释器，3.13 与 3.11 依赖树未必一样；再 `pip check` 看冲突、确认锁文件没被绕过；最后 ModuleNotFoundError 多半是 `sys.path[0]` 变了，用 `python -I` 隔离重跑即显形。

相对导入报 no known parent package 就退回 `python -m`。下表按现象、根因、修法列成速查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 全局 pip install 后两个项目互相覆盖 | 系统解释器只有一个 site-packages，A 项目要 Django 4、B 项目要 Django 5，后装的会覆盖前者的文件，且 pip 不记录生产环境到底装了什么 | 每个项目建独立 venv，用 python -m pip 安装，并把依赖写进 pyproject.toml 加锁文件 |
| requirements.txt 里写 pandas>=1.5 就当锁文件用 | >= 只给下界，解析时可能拿到 1.5 或 2.2，而 2.x 改过 groupby 的默认行为，本地和 CI 装到不同版本就得到不同结果 | 用 uv.lock 或 pip freeze 导出精确 == 与哈希，CI 加 pip install --require-hashes -r requirements.lock |
| 用 python pkg/mod.py 运行带相对导入的包 | 直接跑脚本时 sys.path[0] 是 pkg 目录、__package__ 为空，from . import helper 抛 ImportError: attempted relative import with no known parent package | 改用 python -m pkg.mod，以模块方式执行，让包上下文与相对导入成立 |

<Callout type="warn" title='本讲最容易踩的坑' text='全局 pip install 后两个项目互相覆盖：系统解释器只有一个 site-packages，A 项目要 Django 4、B 项目要 Django 5，后装的会覆盖前者的文件，且 pip 不记录生产环境到底装了什么' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：全局 pip install 后两个项目互相", "body": "系统解释器只有一个 site-packages，A 项目要 Django 4、B 项目要 Django 5，后装的会覆盖前者的文件，且 pip 不记录生产环境到底装了什么", "tip": "每个项目建独立 venv，用 python -m pip 安装，并把依赖写进 pyproject.toml 加锁文件"}, {"title": "第 2 步：requirements.txt 里写 pa", "body": "&gt;= 只给下界，解析时可能拿到 1.5 或 2.2，而 2.x 改过 groupby 的默认行为，本地和 CI 装到不同版本就得到不同结果", "tip": "用 uv.lock 或 pip freeze 导出精确 == 与哈希，CI 加 pip install --require-hashes -r requirements.lock"}, {"title": "第 3 步：用 python pkg/mod.py 运行", "body": "直接跑脚本时 sys.path[0] 是 pkg 目录、__package__ 为空，from . import helper 抛 ImportError: attempted relative import with no known parent package", "tip": "改用 python -m pkg.mod，以模块方式执行，让包上下文与相对导入成立"}]' />


## 把三个变量写进配置：练习、自测与速记

<Exercise title='基础：读出解释器的四个身份字段' task='写函数 env_id() 返回 dict，含 version（用 %d.%d 格式化 version_info 前两位）、executable、in_venv（比较 prefix 与 base_prefix）、impl（implementation.name），并打印 version 与 in_venv。' solution='import sys\ndef env_id():\n    return {&#39;version&#39;: &#39;%d.%d&#39; % sys.version_info[:2],\n            &#39;executable&#39;: sys.executable,\n            &#39;in_venv&#39;: sys.prefix != sys.base_prefix,\n            &#39;impl&#39;: sys.implementation.name}\nr = env_id()\nprint(&#39;version&#39;, r[&#39;version&#39;])\nprint(&#39;in_venv&#39;, r[&#39;in_venv&#39;])' explain='version_info 是具名元组，用 %d.%d 取前两位；in_venv 靠 prefix 与 base_prefix 是否相等（PEP 405）；impl 把 CPython/PyPy 与语言版本区分开，不随 minor 版本变化。' />

<Exercise title='进阶：检测两份依赖锁是否漂移' task='给定两份 requirements 文本，用 hashlib.sha256 比较摘要是否一致，并逐行解析出包名与 == 后的精确版本，打印版本不一致的项。' solution='import hashlib\ndef lock_diff(a, b):\n    same = hashlib.sha256(a.encode()).digest() == hashlib.sha256(b.encode()).digest()\n    def parse(text):\n        out = {}\n        for line in text.splitlines():\n            if &#39;==&#39; in line:\n                k, v = line.split(&#39;==&#39;, 1)\n                out[k] = v\n        return out\n    pa, pb = parse(a), parse(b)\n    return same, {k: (pa.get(k), pb.get(k)) for k in pa if pa.get(k) != pb.get(k)}\na = &#39;requests==2.32.3&#39; + chr(10) + &#39;click==8.1.7&#39;\nb = &#39;requests==2.32.3&#39; + chr(10) + &#39;click==8.2.0&#39;\nprint(lock_diff(a, b))' explain='摘要不同说明锁文件字节发生变化；逐行解析后能定位到具体是哪个包从 8.1.7 漂到 8.2.0。用 chr(10) 造换行可避免在示例字符串里写反斜杠转义。' />

<Quiz no='002-1' q='判断当前是否运行在虚拟环境里，最可靠的写法是？' :options='["sys.prefix != sys.base_prefix", "检查 PATH 里有没有 .venv 字样", "venv 出现在 sys.version 里", "sys.executable 以 python3 结尾"]' answer="0" explain='PEP 405 规定 venv 内 sys.prefix 指向 venv 目录、sys.base_prefix 指向系统前缀；PATH 字符串、version 文本与可执行文件后缀都不能作为判据，手动改 PATH 不等于创建了 venv。' />

<Quiz no='002-2' q='关于 pyproject.toml 与锁文件，哪项描述准确？' :options='["[project].dependencies 是抽象约束，锁文件固定整棵依赖树的精确版本与哈希", "pyproject.toml 本身就是锁文件，CI 直接读它即可", "pip install --require-hashes 会重新解析版本范围", "国内镜像 -i 会改变解析出的版本号"]' answer="0" explain='抽象声明表达能接受的范围，锁文件把含间接依赖的整棵树钉到 == 与 sha256；--require-hashes 要求每条都有哈希且不做范围解析，-i 只换下载源。' />

<Quiz no='002-3' q='python -m pkg.mod 与 python pkg/mod.py 的关键差别是？' :options='["前者 sys.path[0] 是当前工作目录且 __package__ 正确，后者把脚本目录放进路径、相对导入会失败", "两者完全等价", "前者一定更快", "后者会自动激活 venv"]' answer="0" explain='-m 由 runpy 以模块方式执行，保留包上下文；直接跑脚本时解释器把脚本所在目录塞进 sys.path[0]，__package__ 为空，包内相对导入因此抛 ImportError。' />

<Predict no='002-4' q='在未激活 venv、用系统解释器运行本讲主示例时，print(&#39;in_venv&#39;, report[&#39;in_venv&#39;]) 输出什么？' :options='["in_venv False", "in_venv True", "抛出 AttributeError"]' answer='0' output='in_venv False' explain='未进 venv 时 sys.prefix 与 sys.base_prefix 指向同一系统前缀，二者相等，取 != 得到 False；激活 venv 后才变 True。该表达式只比较两个字段，不会抛异常。' />

<FillBlank no='002-5' tpl='___ os, sys, site' :answers='["import"]' hint='回想本讲关于 CPython 与 PyPy 等实现 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 解释器版本：sys 里能读到的四个字段 的落点。' />

<KnowledgeCard :points='["venv 判定：sys.prefix != sys.base_prefix（PEP 405，3.3 起）；激活脚本只改 PATH", "sys.version_info &gt;= (3, 8) 是官方门槛写法，别用 sys.version 字符串做字典序比较", "python -m pip 绑定当前解释器；裸 pip 可能把包装进另一套 site-packages", "pyproject.toml 声明抽象依赖，锁文件固定整棵树精确版本加 sha256；CI 用 --require-hashes", "python -m pkg.mod 以模块执行、相对导入可用；python pkg/mod.py 把脚本目录塞进 sys.path[0]", "import 命中 sys.path 首个匹配并缓存进 sys.modules，磁盘改动需重启进程或 importlib.reload"]' :pitfalls='["全局 pip install 后两个项目互相覆盖", "requirements.txt 里写 pandas&gt;=1.5 就当锁文件用", "用 python pkg/mod.py 运行带相对导入的包", "全局 pip install 会让两个项目互相污染，且最终无法说清生产环境到底装了什么"]' summary='环境问题的本质是三个变量没对齐：解释器版本、依赖集合、工作目录；把它们全部写进配置文件，换机器才能一行复原' />

1. venv 判定：sys.prefix != sys.base_prefix（PEP 405，3.3 起）；激活脚本只改 PATH

2. sys.version_info >= (3, 8) 是官方门槛写法，别用 sys.version 字符串做字典序比较

3. python -m pip 绑定当前解释器；裸 pip 可能把包装进另一套 site-packages

[下一讲：第一行 Python：从源码到字节码再到执行](/guide/hello)
