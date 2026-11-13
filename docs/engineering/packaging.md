---
title: 第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI
description: 把项目做成别人一行命令能装的东西
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='40 分钟' goal='把项目做成别人一行命令能装的东西' prereq='第 079 讲 · 配置管理：环境变量、.env 与配置中心' />

# 第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI

配置与密钥都安顿好了，轮到把项目打包与发布出去：让别人一行命令就能装上。一个内部工具只传了源码包，用户安装时还得本地跑一遍构建，缺依赖就装不上；另一个把测试和本机绝对路径塞进产物，体积翻倍还漏了内部文件名。

从构建后端与 PEP 517 说起，讲清 wheel 与 sdist 的差别，再用 console_scripts 声明命令行入口，接着整理版本号与元数据，最后用 build 加 twine check 校验。带着 pyproject、依赖与模块基础来；学完能把项目做成一行命令装得上的产物，版本号与 tag 交给流水线，也给下一讲的闭环留好起点。


## 只传了 sdist，用户 pip install 时还得本地跑一遍构建后端

一个内部工具只往 PyPI 传了 sdist，用户 pip install 时还得在本地跑一遍构建后端，缺编译依赖就失败，工单里全是「装不上」；另一个包把 tests/ 和本地绝对路径一起打进了 wheel，体积翻了十倍还泄漏了内部文件名；还有人忘了声明 console_scripts，装完包命令行里压根没有可执行入口。

打包的目标不是「能生成文件」，而是让别人一行命令装上、且装上的是组织好的产物而非源码。wheel 与 sdist 的差别、PEP 517 构建后端、入口点与元数据、发布流水线的校验，决定了这个目标能否达成。本讲把 pyproject、wheel 结构、console_scripts 与发布清单讲到能一条命令交付。

<Callout type="warn" title='先看一个真实会出错的写法' text='只上传 sdist 不上传 wheel：用户安装时还要跑构建后端，缺编译依赖或后端就失败' />


## PEP 517 构建前端与后端：隔离环境里发生了什么

PEP 518 的 `[build-system]` 声明 requires（构建依赖，如 setuptools>=68）与 build-backend（如 `setuptools.build_meta`、`hatchling.build`、`flit_core.buildapi`、`poetry.core.masonry`.api）；

PEP 517 规定前端 python -m build 通过隔离环境调用后端的 build_sdist / build_wheel 钩子，产物落在 dist/，可用 --sdist、--wheel、--no-isolation 控制。

sdist 是源码分发（.`tar.gz`），含源码与 `pyproject.toml`/`setup.py`，安装时还要再跑一次构建后端，依赖构建工具、失败率更高。

wheel（PEP 427）是已构建分发，本质是一个 ZIP，文件名遵循 &#123;name&#125;-&#123;version&#125;-&#123;python tag&#125;-&#123;abi tag&#125;-&#123;platform tag&#125;.whl：例如 pkg-1.2.3-py3-none-`any.whl`（纯 Python 通用）与 cp313-cp313-`macosx_11_0_arm64.whl`（特定 CPython 与平台）。

安装 wheel 只是把内容解压到 site-packages，不执行构建代码，因此应同时上传 sdist 与 wheel，且优先保证 wheel 可用。

wheel 里含 &lt;name>/ 包目录与 &lt;name>-&lt;version>.dist-info/：METADATA、WHEEL、RECORD、`entry_points.txt`。

<Callout type="tip" title='核心心智模型' text='PEP 518 的 [build-system] 声明 requires（构建依赖，如 setuptools&gt;=68）与 build-backend（如 setuptools.build_meta、hatchling.build、flit_core.buildapi、poetry.core.maso' />

python -m build 作为 PEP 517 前端，在隔离环境里安装 `[build-system]`.requires，再调用 build-backend 的 build_wheel/build_sdist 钩子；

wheel 产物是符合 PEP 427 的 ZIP，文件名里的 python/abi/platform 三段标签让 pip 无需执行代码就能判断兼容性，纯 py3-none-any 装到 purelib、带 cp313 与平台标签的装到 platlib。

安装器把包目录解压到 site-packages，并把 .dist-info/METADATA（RFC 822 风格头，`email.message_from_bytes` 可解析）、WHEEL、RECORD、`entry_points.txt` 一并落地；

RECORD 是 path,sha256=&lt;hash>,&lt;size> 的 CSV，pip 用它校验完整性并支持精确卸载。

`[console_scripts]` 下的 `name = module`:attr 被安装器翻译成平台相关的启动包装脚本，`importlib.metadata.distribution()`.entry_points 将其暴露成 EntryPoint 对象。

sdist 不含这些组织好的产物，安装时必须重跑构建钩子，这正是「只传 sdist 失败率高」的机制原因。

<ConceptDiagram type='flow3' title='第 080 讲 · 构建后端与 PEP 517，sdist vs wheel' labels='构建后端与 PEP 517，sdist vs|元数据、入口点与版本|发布流水线与校验清单' caption='把项目做成别人一行命令能装的东西' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### build-backend 被调用时装了哪些 requires

```python
import sys

wheels = ['demo-1.2.3-py3-none-any.whl',
          'demo-1.2.3-cp313-cp313-macosx_11_0_arm64.whl',
          'demo-1.2.3.tar.gz']

def is_wheel(n):
    return n.endswith('.whl')

def tags(n):
    return n[:-4].split('-')[-3:]

print('wheel vs sdist', [is_wheel(w) for w in wheels])
print('pure tag', tags(wheels[0]))
print('platform tag', tags(wheels[1])[-1])
print('python', sys.version_info[0], sys.version_info[1])
```

<OutputBox title='原理验证' output='wheel vs sdist [True, True, False]\npure tag [&#39;py3&#39;, &#39;none&#39;, &#39;any&#39;]\nplatform tag macosx_11_0_arm64\npython 3 13' />


## sdist 与 wheel 到底差在哪

**sdist 与 wheel 对照**

| 维度 | sdist (.tar.gz) | wheel (.whl) |
| --- | --- | --- |
| 本质 | 源码分发 | 已构建分发，ZIP 归档 |
| 安装时 | 再跑一次构建后端 | 仅解压到 site-packages |
| 构建依赖 | 需要，失败率更高 | 不需要 |
| 文件名标签 | 无兼容标签 | python-abi-platform 三段标签 |
| 内容 | 源码 + pyproject/setup.py | 包 + .dist-info/METADATA/RECORD 等 |
| 发布建议 | 应一并上传 | 优先保证可用，用户装它 |

```python
import zipfile, os, tempfile, email

name = 'demo_pkg'
version = '1.2.3'
wheel = name + '-' + version + '-py3-none-any.whl'
dist_info = name + '-' + version + '.dist-info'

metadata = chr(10).join([
    'Metadata-Version: 2.1',
    'Name: ' + name,
    'Version: ' + version,
    'Requires-Python: >=3.9',
    'Requires-Dist: requests>=2.28',
])
wheel_meta = chr(10).join([
    'Wheel-Version: 1.0',
    'Generator: demo',
    'Root-Is-Purelib: true',
    'Tag: py3-none-any',
])
entry_points = '[console_scripts]' + chr(10) + 'demo-cli = demo_pkg.cli:main' + chr(10)

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, wheel)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(dist_info + '/METADATA', metadata)
        z.writestr(dist_info + '/WHEEL', wheel_meta)
        z.writestr(dist_info + '/entry_points.txt', entry_points)
        z.writestr(dist_info + '/RECORD', '')
        z.writestr(name + '/__init__.py', 'VERSION = "1.2.3"' + chr(10))
        z.writestr(name + '/cli.py', 'def main():' + chr(10) + '    return 0' + chr(10))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print('wheel entries', len(names))
        print('has METADATA', dist_info + '/METADATA' in names)
        msg = email.message_from_bytes(z.read(dist_info + '/METADATA'))
        print('Name field', msg['Name'])
        print('Requires-Dist', msg['Requires-Dist'])
        ep = z.read(dist_info + '/entry_points.txt').decode()
        print('entry point', ep.split('=')[1].strip())
```

<OutputBox title='主示例运行结果' output='wheel entries 6\nhas METADATA True\nName field demo_pkg\nRequires-Dist requests&gt;=2.28\nentry point demo_pkg.cli:main' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import zipfile, os, tempfile, email\n\nname = &#39;demo_pkg&#39;\nversion = &#39;1.2.3&#39;\nwheel = name + &#39;-&#39; + version + &#39;-py3-none-any.whl&#39;\ndist_info = name + &#39;-&#39; + version + &#39;.dist-info&#39;\n\nmetadata = chr(10).join([\n    &#39;Metadata-Version: 2.1&#39;,\n    &#39;Name: &#39; + name,\n    &#39;Version: &#39; + version,\n    &#39;Requires-Python: &gt;=3.9&#39;,\n    &#39;Requires-Dist: requests&gt;=2.28&#39;,\n])\nwheel_meta = chr(10).join([\n    &#39;Wheel-Version: 1.0&#39;,\n    &#39;Generator: demo&#39;,\n    &#39;Root-Is-Purelib: true&#39;,\n    &#39;Tag: py3-none-any&#39;,\n])\nentry_points = &#39;[console_scripts]&#39; + chr(10) + &#39;demo-cli = demo_pkg.cli:main&#39; + chr(10)\n\nwith tempfile.TemporaryDirectory() as d:\n    path = os.path.join(d, wheel)\n    with zipfile.ZipFile(path, &#39;w&#39;) as z:\n        z.writestr(dist_info + &#39;/METADATA&#39;, metadata)\n        z.writestr(dist_info + &#39;/WHEEL&#39;, wheel_meta)\n        z.writestr(dist_info + &#39;/entry_points.txt&#39;, entry_points)\n        z.writestr(dist_info + &#39;/RECORD&#39;, &#39;&#39;)\n        z.writestr(name + &#39;/__init__.py&#39;, &#39;VERSION = "1.2.3"&#39; + chr(10))\n        z.writestr(name + &#39;/cli.py&#39;, &#39;def main():&#39; + chr(10) + &#39;    return 0&#39; + chr(10))\n    with zipfile.ZipFile(path) as z:\n        names = z.namelist()\n        print(&#39;wheel entries&#39;, len(names))\n        print(&#39;has METADATA&#39;, dist_info + &#39;/METADATA&#39; in names)\n        msg = email.message_from_bytes(z.read(dist_info + &#39;/METADATA&#39;))\n        print(&#39;Name field&#39;, msg[&#39;Name&#39;])\n        print(&#39;Requires-Dist&#39;, msg[&#39;Requires-Dist&#39;])\n        ep = z.read(dist_info + &#39;/entry_points.txt&#39;).decode()\n        print(&#39;entry point&#39;, ep.split(&#39;=&#39;)[1].strip())' :notes='["导入 zipfile 读写 wheel、os/tempfile 建临时文件、email 解析元数据", "包名与版本号，决定 wheel 与 dist-info 目录名", "wheel 文件名遵循 name-version-python-abi-platform.whl", "dist-info 目录名 = name + &#39;-&#39; + version + &#39;.dist-info&#39;", "用 chr(10) 拼出 METADATA 的 RFC 822 风格头", "声明元数据版本", "Name 字段是分发名", "Version 字段是 PEP 440 版本", "Requires-Python 限定解释器", "Requires-Dist 声明运行依赖", "WHEEL 文件记录 wheel 规范版本与标签", "Generator 标明生成工具", "Root-Is-Purelib: true 表示装到 purelib", "Tag: py3-none-any 表示纯 Python 通用 wheel", "entry_points.txt 里 [console_scripts] 声明 CLI 入口", "临时目录里创建这个 wheel（ZIP）文件", "以写模式打开 ZIP", "写入 METADATA", "写入 WHEEL", "写入 entry_points.txt", "写入 RECORD（此处占位为空）", "写入包 __init__.py", "写入 cli.py 的 main 函数", "以读模式重新打开校验", "列出所有条目数量", "确认 METADATA 存在", "用 email 解析 METADATA 头", "读出 Name 字段", "读出运行依赖 Requires-Dist", "读出并解析 console_scripts 的调用目标", "PEP 518 [build-system] 声明 requires 与 build-backend；PEP 517 前端 python -m build 调 build_wheel/build_sdist", "sdist 是源码、安装要重跑构建；wheel 是 PEP 427 ZIP、安装只解压，二者都要上传且优先保证 wheel", "wheel 名 {name}-{version}-{python}-{abi}-{platform}.whl；py3-none-any 通用，cp313-... 平台相关", ".dist-info 含 METADATA（PEP 621）、WHEEL（Root-Is-Purelib/Tag）、RECORD（path,sha256,size）、entry_points.txt", "[project.scripts] 声明 console_scripts 入口，importlib.metadata 读回；版本遵循 PEP 440 由流水线统一", "发布闸门：build → twine check → zipfile 查条目 → 干净 venv 装 whl 冒烟；鉴权用 Trusted Publishing(OIDC)", "PEP 518 [build-system] 声明 requires 与 build-backend；PEP 517 前端 python -m build 调 build_wheel/build_sdist"]' title='第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import sys, os, tempfile
import importlib.metadata as im
import importlib
importlib.invalidate_caches()

with tempfile.TemporaryDirectory() as d:
    di = os.path.join(d, 'demo_cli_xyz-1.2.3.dist-info')
    os.makedirs(di)
    open(os.path.join(di, 'METADATA'), 'w').write('Metadata-Version: 2.1' + chr(10) + 'Name: demo-cli-xyz' + chr(10) + 'Version: 1.2.3' + chr(10))
    open(os.path.join(di, 'entry_points.txt'), 'w').write('[console_scripts]' + chr(10) + 'demo-xyz = demo_cli_xyz:main' + chr(10))
    sys.path.insert(0, d)
    dist = im.distribution('demo-cli-xyz')
    eps = [e for e in dist.entry_points if e.group == 'console_scripts']
    print('entry found', len(eps) == 1)
    print('target', eps[0].value)
    print('dist version', dist.version)
    sys.path.remove(d)
```

<OutputBox title='对照写法：先自己猜，再点开' output='entry found True\ntarget demo_cli_xyz:main\ndist version 1.2.3' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import zipfile, os, tempfile, email\n\nname = &#39;demo_pkg&#39;\nversion = &#39;1.2.3&#39;\nwheel = name + &#39;-&#39; + version + &#39;-py3-none-any.whl&#39;\ndist_info = name + &#39;-&#39; + version + &#39;.dist-info&#39;\n\nmetadata = chr(10).join([\n    &#39;Metadata-Version: 2.1&#39;,\n    &#39;Name: &#39; + name,\n    &#39;Version: &#39; + version,\n    &#39;Requires-Python: &gt;=3.9&#39;,\n    &#39;Requires-Dist: requests&gt;=2.28&#39;,\n])\nwheel_meta = chr(10).join([\n    &#39;Wheel-Version: 1.0&#39;,\n    &#39;Generator: demo&#39;,\n    &#39;Root-Is-Purelib: true&#39;,\n    &#39;Tag: py3-none-any&#39;,\n])\nentry_points = &#39;[console_scripts]&#39; + chr(10) + &#39;demo-cli = demo_pkg.cli:main&#39; + chr(10)\n\nwith tempfile.TemporaryDirectory() as d:\n    path = os.path.join(d, wheel)\n    with zipfile.ZipFile(path, &#39;w&#39;) as z:\n        z.writestr(dist_info + &#39;/METADATA&#39;, metadata)\n        z.writestr(dist_info + &#39;/WHEEL&#39;, wheel_meta)\n        z.writestr(dist_info + &#39;/entry_points.txt&#39;, entry_points)\n        z.writestr(dist_info + &#39;/RECORD&#39;, &#39;&#39;)\n        z.writestr(name + &#39;/__init__.py&#39;, &#39;VERSION = \"1.2.3\"&#39; + chr(10))\n        z.writestr(name + &#39;/cli.py&#39;, &#39;def main():&#39; + chr(10) + &#39;    return 0&#39; + chr(10))\n    with zipfile.ZipFile(path) as z:\n        names = z.namelist()\n        print(&#39;wheel entries&#39;, len(names))\n        print(&#39;has METADATA&#39;, dist_info + &#39;/METADATA&#39; in names)\n        msg = email.message_from_bytes(z.read(dist_info + &#39;/METADATA&#39;))\n        print(&#39;Name field&#39;, msg[&#39;Name&#39;])\n        print(&#39;Requires-Dist&#39;, msg[&#39;Requires-Dist&#39;])\n        ep = z.read(dist_info + &#39;/entry_points.txt&#39;).decode()\n        print(&#39;entry point&#39;, ep.split(&#39;=&#39;)[1].strip())", "note": "构建后端与 PEP 517，sdist vs wheel"}, {"label": "对照 / 进阶", "code": "import sys, os, tempfile\nimport importlib.metadata as im\nimport importlib\nimportlib.invalidate_caches()\n\nwith tempfile.TemporaryDirectory() as d:\n    di = os.path.join(d, &#39;demo_cli_xyz-1.2.3.dist-info&#39;)\n    os.makedirs(di)\n    open(os.path.join(di, &#39;METADATA&#39;), &#39;w&#39;).write(&#39;Metadata-Version: 2.1&#39; + chr(10) + &#39;Name: demo-cli-xyz&#39; + chr(10) + &#39;Version: 1.2.3&#39; + chr(10))\n    open(os.path.join(di, &#39;entry_points.txt&#39;), &#39;w&#39;).write(&#39;[console_scripts]&#39; + chr(10) + &#39;demo-xyz = demo_cli_xyz:main&#39; + chr(10))\n    sys.path.insert(0, d)\n    dist = im.distribution(&#39;demo-cli-xyz&#39;)\n    eps = [e for e in dist.entry_points if e.group == &#39;console_scripts&#39;]\n    print(&#39;entry found&#39;, len(eps) == 1)\n    print(&#39;target&#39;, eps[0].value)\n    print(&#39;dist version&#39;, dist.version)\n    sys.path.remove(d)", "note": "元数据、入口点与版本"}]' title='两种写法对照' note='差异集中在 构建后端与 PEP 517；先看输出，再找背后的规则。' />


## wheel 文件名标签、dist-info 与 RECORD

**wheel 文件名标签与 dist-info 内容**

| 项 | 示例 / 字段 | 含义 |
| --- | --- | --- |
| py3-none-any | 纯 Python 通用 | 装到 purelib，任意平台可用 |
| cp313-cp313-macosx_11_0_arm64 | CPython 3.13 + macOS arm64 | 含 C 扩展的平台 wheel |
| METADATA | Name / Version / Requires-Python / Requires-Dist | PEP 621 元数据，RFC 822 头 |
| WHEEL | Wheel-Version / Generator / Root-Is-Purelib / Tag | wheel 规范与兼容性标签 |
| RECORD | path,sha256=&lt;hash>,&lt;size> | 完整性与卸载清单 |
| entry_points.txt | [console_scripts] mycli = pkg.cli:main | 生成命令行包装脚本 |

<Term word='构建后端与 PEP 517' text='PEP 518 的 [build-system] 声明 requires（构建依赖，如 setuptools&gt;=68）与 build-backend（如 setuptools.build_meta、hatchling.build、flit_core.buildapi、poetry.core.masonry.api）；P' />

<Term word='wheel / sdist 差别' text='PEP 621 把元数据集中在 [project]：name、version、description、readme、requires-python、license、authors、dependencies、optional-dependencies、scripts、entry-points，版本也可 dynamic =' />


## 元数据、console_scripts 入口点与版本

PEP 621 把元数据集中在 `[project]`：name、version、description、readme、requires-python、license、authors、dependencies、optional-dependencies、scripts、entry-points，版本也可 dynamic = ['version'] 从 `__version__` 或 SCM 读取。

命令行入口写在 `[project.scripts]`：mycli = 'mypkg.cli:main'，安装器据此在 bin/Scripts 生成可执行包装脚本；

运行时用 `importlib.metadata.distribution`('x').entry_points 或 entry_points(group='console_scripts')（3.10+ 的 select 式 API）读出 group/name/value，`importlib.metadata.version`('x') 读版本。

版本号遵循 PEP 440：1.2.3、1.2.3rc1、1.2.3.post1、1.2.3.dev1、+local 分别表正式、预发布、修订、开发、本地版本；流水线统一用 git tag 生成版本与 CHANGELOG，避免手工改号漂移。

WHEEL 文件里的 Root-Is-Purelib: true 与 Tag: py3-none-any 决定装到 purelib 还是 platlib；RECORD 是 path,sha256=&lt;hash>,&lt;size> 的 CSV，供 pip 校验完整性与卸载。

```bash
python -m pip check
```

把输入换成你自己的数据，观察结果是否仍符合 **构建后端与 PEP 517** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 发布流水线步骤与校验清单

可靠发布是一条可重复的闸门：python -m build 同时产出 wheel 与 sdist → twine check dist/* 校验 METADATA 与 README 渲染 → 先传 TestPyPI 验证安装 → 再传 PyPI。

鉴权优先用 Trusted Publishing（OIDC，如 pypa/gh-action-pypi-publish，无需长期 token），退而求其次才用 `TWINE_USERNAME=__token__` + TWINE_PASSWORD。

发布前用 zipfile 检查 wheel 内容：确认没有 tests/、临时路径、开发依赖被打包，确认 RECORD 行数与文件数吻合，确认 `entry_points.txt` 里 console_scripts 目标可导入。

干净虚拟环境里 pip install dist/`x.whl` 后 import 并跑 --help，是「别人能一行命令装上」的最终验收；版本号、tag、CHANGELOG 由流水线统一管理，出问题用 yank 而非删除已上传版本。

把 build、twine check、安装冒烟写成 CI 步骤，发布才不依赖某台机器的手工操作。

**发布流水线步骤与校验**

| 步骤 | 命令 / 机制 | 校验点 |
| --- | --- | --- |
| 构建 | python -m build | dist/ 同时有 whl 与 tar.gz |
| 元数据检查 | twine check dist/* | README 渲染与 METADATA 合法 |
| 内容检查 | zipfile 列出 wheel 条目 | 无 tests/、本地路径、开发依赖 |
| 安装冒烟 | 干净 venv 里 pip install x.whl | import 与 --help 可用 |
| 鉴权 | Trusted Publishing (OIDC) | 避免长期 API token |
| 版本与回滚 | git tag + CHANGELOG，异常用 yank | 版本由流水线统一，不删已传版本 |

<FlowTimeline :steps='[{"title": "构建后端与 PEP 517，sdist vs wheel", "desc": "PEP 518 的 [build-system] 声明 requires（构建依赖，…", "tone": "blue"}, {"title": "元数据、入口点与版本", "desc": "PEP 621 把元数据集中在 [project]：name、version、des…", "tone": "purple"}, {"title": "发布流水线与校验清单", "desc": "可靠发布是一条可重复的闸门：python -m build 同时产出 wheel 与…", "tone": "orange"}, {"title": "工程落地", "desc": "发布前自检：构建 wheel 并核对元数据与 RECORD", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 发布前自检：构建 wheel 并核对元数据与 RECORD

把发布前的校验写成脚本，比人工点开 dist/ 可靠得多：用 zipfile 组装一个符合 PEP 427 的最小 wheel（METADATA、WHEEL、`entry_points.txt`、包代码、RECORD），再用 email 解析 METADATA、用 hashlib 为 RECORD 生成每行的 sha256 与大小，最后读回验证 Name/Version/Requires-Dist、pure 标签与 RECORD 行数。

真实项目把「组装」换成 python -m build 的产物、把读回换成 twine check 与干净 venv 安装冒烟即可。重点看 wheel 里每个文件都有可核对的元数据与完整性记录。

```python
import zipfile, os, tempfile, email, hashlib

NAME, VERSION = 'reportkit', '0.4.0'
di = NAME + '-' + VERSION + '.dist-info'
metadata = chr(10).join([
    'Metadata-Version: 2.1', 'Name: ' + NAME, 'Version: ' + VERSION,
    'Requires-Python: >=3.10', 'Requires-Dist: requests>=2.31',
    'Summary: report helpers'])
entry = '[console_scripts]' + chr(10) + 'report = reportkit.cli:main' + chr(10)

with tempfile.TemporaryDirectory() as d:
    whl = os.path.join(d, NAME + '-' + VERSION + '-py3-none-any.whl')
    files = {
        di + '/METADATA': metadata,
        di + '/WHEEL': 'Wheel-Version: 1.0' + chr(10) + 'Root-Is-Purelib: true' + chr(10) + 'Tag: py3-none-any' + chr(10),
        di + '/entry_points.txt': entry,
        NAME + '/__init__.py': '__version__ = "0.4.0"' + chr(10),
        NAME + '/cli.py': 'def main():' + chr(10) + '    print("report")' + chr(10),
    }
    record_lines = []
    with zipfile.ZipFile(whl, 'w') as z:
        for path, content in files.items():
            data = content.encode()
            z.writestr(path, data)
            record_lines.append(path + ',sha256=' + hashlib.sha256(data).hexdigest()[:12] + ',' + str(len(data)))
        z.writestr(di + '/RECORD', chr(10).join(record_lines) + chr(10))
    with zipfile.ZipFile(whl) as z:
        msg = email.message_from_bytes(z.read(di + '/METADATA'))
        print('name', msg['Name'], 'version', msg['Version'])
        print('requires', msg['Requires-Dist'])
        print('pure wheel', 'true' in z.read(di + '/WHEEL').decode())
        print('record rows', len(z.read(di + '/RECORD').decode().splitlines()))
```

<Callout type="idea" title='落地提示' text='用 build + twine check 做发布前校验，入口点声明 CLI，版本号与 tag 由流水线统一管理' />

<CheckList id='P080b' title='上线前自检' :items='["能复现并解释「只上传 sdist 不上传 wheel」", "能复现并解释「把 tests/、本地路径、开发依赖打进 wheel」", "能复现并解释「不声明 console_scripts、版本与 tag 各改」", "能用一条命令验证 构建后端与 PEP 517", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只上传 sdist 不上传 wheel | 用户安装时还要跑构建后端，缺编译依赖或后端就失败 | python -m build 同时产出 wheel 与 sdist 并一起 twine upload，优先保证 wheel 可装 |
| 把 tests/、本地路径、开发依赖打进 wheel | 体积膨胀甚至泄漏内部文件，生产环境装上无关内容 | 发布前用 zipfile 检查条目与 RECORD，配 package-data / exclude，把测试放包外 |
| 不声明 console_scripts、版本与 tag 各改各的、用长期 token | 装完没有 CLI 入口、无法回滚、token 泄漏风险高 | [project.scripts] 声明入口，版本/CHANGELOG/tag 由流水线统一，鉴权改用 Trusted Publishing(OIDC) |

<Callout type="warn" title='本讲最容易踩的坑' text='只上传 sdist 不上传 wheel：用户安装时还要跑构建后端，缺编译依赖或后端就失败' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只上传 sdist 不上传 wheel", "body": "用户安装时还要跑构建后端，缺编译依赖或后端就失败", "tip": "python -m build 同时产出 wheel 与 sdist 并一起 twine upload，优先保证 wheel 可装"}, {"title": "第 2 步：把 tests/、本地路径、开发依赖打进 w", "body": "体积膨胀甚至泄漏内部文件，生产环境装上无关内容", "tip": "发布前用 zipfile 检查条目与 RECORD，配 package-data / exclude，把测试放包外"}, {"title": "第 3 步：不声明 console_scripts、版本", "body": "装完没有 CLI 入口、无法回滚、token 泄漏风险高", "tip": "[project.scripts] 声明入口，版本/CHANGELOG/tag 由流水线统一，鉴权改用 Trusted Publishing(OIDC)"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：从 wheel 文件名读出兼容标签' task='对 pkg-1.2.3-py3-none-any.whl 判断是否 wheel、取出末三段标签并打印。' solution='name = &#39;pkg-1.2.3-py3-none-any.whl&#39;\nprint(&#39;pure&#39;, name.endswith(&#39;.whl&#39;), &#39;tags&#39;, name[:-4].split(&#39;-&#39;)[-3:])' explain='wheel 名末三段是 python-abi-platform 标签；py3-none-any 表示纯 Python 通用，pip 据此选件无需执行代码。' />

<Exercise title='进阶：确认 importlib.metadata 的入口点 API' task='打印 importlib.metadata 是否有 entry_points 与 distribution 两个函数。' solution='import importlib.metadata as im\nprint(&#39;has entry_points&#39;, hasattr(im, &#39;entry_points&#39;))\nprint(&#39;has distribution&#39;, hasattr(im, &#39;distribution&#39;))' explain='3.10+ 用 entry_points(group=&#39;console_scripts&#39;) 或 distribution(name).entry_points 读取入口点；安装器据 entry_points.txt 生成 CLI 包装脚本。' />

<Quiz no='080-1' q='wheel 相比 sdist 的关键优势是？' :options='["已构建、安装只解压不跑构建后端，兼容标签让 pip 选件", "体积一定更小", "包含完整源码便于阅读", "不需要 .dist-info"]' answer="0" explain='wheel 是 PEP 427 的 ZIP，文件名带 python/abi/platform 标签，安装仅解压到 site-packages；sdist 安装时仍要重跑构建钩子，失败率更高。' />

<Quiz no='080-2' q='[project.scripts] mycli = &#39;mypkg.cli:main&#39; 的作用是？' :options='["声明 console_scripts 入口，安装后生成命令行可执行包装", "声明运行依赖", "指定构建后端", "设置版本号"]' answer="0" explain='PEP 621 的 scripts 写入口点，安装器在 bin/Scripts 生成包装脚本；importlib.metadata 可用 entry_points(group=&#39;console_scripts&#39;) 读回。' />

<Quiz no='080-3' q='发布前用 twine check dist/* 主要校验什么？' :options='["METADATA 与 README 的渲染是否合法", "wheel 运行速度", "单元测试是否通过", "依赖是否有 CVE"]' answer="0" explain='twine check 解析长描述与元数据、验证在 PyPI 页面能否正确渲染；配合 zipfile 查条目、干净 venv 装 whl 冒烟，构成发布闸门。' />

<Predict no='080-P' q='对 demo-1.2.3-py3-none-any.whl 取末三段标签，输出是？' :options='["[&#39;py3&#39;, &#39;none&#39;, &#39;any&#39;]", "[&#39;cp313&#39;, &#39;cp313&#39;, &#39;any&#39;]", "[&#39;py3&#39;, &#39;none&#39;, &#39;macosx&#39;]"]' answer='0' output='[&#39;py3&#39;, &#39;none&#39;, &#39;any&#39;]' explain='wheel 文件名去掉 .whl 后按 &#39;-&#39; 切分，末三段依次是 python tag、abi tag、platform tag；py3-none-any 表示任意 Python 3、无 ABI 约束、任意平台。' />

<FillBlank no='080-F' tpl='___ zipfile, os, tempfile, email' :answers='["import"]' hint='回想本讲关于 构建后端与 PEP 517 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 构建后端与 PEP 517，sdist vs wheel 的落点。' />

<KnowledgeCard :points='["PEP 518 [build-system] 声明 requires 与 build-backend；PEP 517 前端 python -m build 调 build_wheel/build_sdist", "sdist 是源码、安装要重跑构建；wheel 是 PEP 427 ZIP、安装只解压，二者都要上传且优先保证 wheel", "wheel 名 {name}-{version}-{python}-{abi}-{platform}.whl；py3-none-any 通用，cp313-... 平台相关", ".dist-info 含 METADATA（PEP 621）、WHEEL（Root-Is-Purelib/Tag）、RECORD（path,sha256,size）、entry_points.txt", "[project.scripts] 声明 console_scripts 入口，importlib.metadata 读回；版本遵循 PEP 440 由流水线统一", "发布闸门：build → twine check → zipfile 查条目 → 干净 venv 装 whl 冒烟；鉴权用 Trusted Publishing(OIDC)"]' :pitfalls='["只上传 sdist 不上传 wheel", "把 tests/、本地路径、开发依赖打进 wheel", "不声明 console_scripts、版本与 tag 各改各的、用长期 token", "把测试数据、本地路径、开发依赖打进 wheel，会让包体积膨胀甚至泄漏内部文件"]' summary='wheel 是已经组织好的安装产物，sdist 是源码；只上传 sdist 会让用户在安装时还要跑一遍构建，失败率明显更高' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| PEP 518 [build-system] 声明 requires 与 build-backend；PEP 517 前端 python -m build 调 build_wheel/build_sdist | 建立直觉 |
| sdist 是源码、安装要重跑构建；wheel 是 PEP 427 ZIP、安装只解压，二者都要上传且优先保证 wheel | 跑通示例 |
| wheel 名 &#123;name&#125;-&#123;version&#125;-&#123;python&#125;-&#123;abi&#125;-&#123;platform&#125;.whl；py3-none-any 通用，cp313-... 平台相关 | 深入边界 |
| .dist-info 含 METADATA（PEP 621）、WHEEL（Root-Is-Purelib/Tag）、RECORD（path,sha256,size）、entry_points.txt | 工程落地 |
| [project.scripts] 声明 console_scripts 入口，importlib.metadata 读回；版本遵循 PEP 440 由流水线统一 | 随堂检测 |
| 发布闸门：build → twine check → zipfile 查条目 → 干净 venv 装 whl 冒烟；鉴权用 Trusted Publishing(OIDC) | 复盘 |

1. PEP 518 [build-system] 声明 requires 与 build-backend；PEP 517 前端 python -m build 调 build_wheel/build_sdist

2. sdist 是源码、安装要重跑构建；wheel 是 PEP 427 ZIP、安装只解压，二者都要上传且优先保证 wheel

3. wheel 名 &#123;name&#125;-&#123;version&#125;-&#123;python&#125;-&#123;abi&#125;-&#123;platform&#125;.whl；py3-none-any 通用，cp313-... 平台相关

[下一讲：阶段综合：把脚本重构成可发布包](/engineering/capstone)
