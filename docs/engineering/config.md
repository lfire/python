---
title: 第 079 讲 · 配置管理：环境变量、.env 与配置中心
description: 把配置做成可验证、可覆盖、可审计的输入
---

<StageHeader stage='L7 · 工程化' level='★★☆☆☆' time='30 分钟' goal='把配置做成可验证、可覆盖、可审计的输入' prereq='第 078 讲 · 日志：logging、结构化日志与追踪关联' />

# 第 079 讲 · 配置管理：环境变量、.env 与配置中心

日志能查了，可配置出错的时机仍很别扭：有人把调试开关写成字符串，解析时被当成真，生产环境就此敞着；也有人把数据库密码硬编码在代码里，轮换一次得全量改代码重新发版。更隐蔽的是某个冷门分支直到半夜才第一次读到空值，排查时对不上任何发布记录。

顺序按可信度来：先立十二要素的环境变量，再用类型化配置对象做启动期校验，接着谈分层覆盖的优先级，然后处理密钥与轮换，最后盯住配置漂移。带着环境变量、类型与模块的概念来；学完能把配置做成可验证、可覆盖、可审计的输入，让错误在启动瞬间就暴露，而不是等某个分支被踩到。


## 密码硬编码在 settings.py，轮换只能全量改代码重新发版

一个服务把数据库密码硬编码在 `settings.py` 里，轮换时只能全量改代码重新发版；另一个服务把 `DEBUG` 写成字符串 `'False'`，解析时用 `bool('False')` 得到 `True`，结果生产环境开了调试模式，把堆栈打给了用户。

还有更隐蔽的：某配置项写错，平时没人调用那个冷门接口，直到半夜第一次读到空字符串才崩，排查时完全对不上发布记录。这几种故障指向同一件事——配置错误的正确暴露时机是启动瞬间，而不是运行期某个分支被踩到。本讲把十二要素的环境变量、类型化校验、分层覆盖优先级、密钥轮换与配置漂移讲到能做成可验证、可审计的输入。


## 十二要素、环境变量与 bool('False') 的类型陷阱

十二要素应用要求配置与代码严格分离、通过环境变量注入。

`os.environ` 的类型是 `os._Environ`（一个 `MutableMapping`），`os.getenv(key, default)` 在取不到时返回默认值，`os.environb` 提供字节版本。

关键陷阱是：所有环境变量的值都是 `str`——`os.environ` 底层是 C 的 `char**` 键值串，不带任何类型信息，所以端口必须 `int(...)` 转换，开关必须自己解析；

`bool('False')` 会得到 `True`，因为任意非空字符串在 Python 里都为真，得写个 `parse_bool` 把 `'1'` / `'true'` / `'yes'` / `'on'` 归一成布尔。

`.env` 文件由 `python-dotenv` 的 `load_dotenv()` 读取，格式是 `KEY=VALUE`；`.env` 必须进 `.gitignore`，提交进仓库的应是去掉真值的 `.env.example` 占位文件。

标准库里，`configparser` 读 INI、`tomllib`（Python 3.11 起）读 `TOML`、`json` 读配置；

其中 `tomllib` 会按 `TOML` 规范把 `false` / `8080` 解析成原生 `bool` / `int`，`tomllib.loads('debug=false')` 得到 `{'debug': False}` 而非字符串，正好和环境变量的全字符串形成对照。

PEP 508 的环境标记与 `argparse` 的命令行覆盖，是另外两类配置入口。

**环境变量与类型转换**

| API / 写法 | 结果 / 类型 | 注意 |
| --- | --- | --- |
| os.environ['K'] | str 或 KeyError | 值永远是字符串 |
| os.getenv('K', 'd') | str 或默认 | 环境变量缺失时用默认 |
| bool('False') | True | 非空字符串皆真，必须 parse_bool |
| int(os.environ['PORT']) | int | 非数字抛 ValueError |
| tomllib.loads('debug=false') | &#123;'debug': False&#125; | TOML 3.11+ 解析成原生 bool |
| configparser | INI 全为 str | 需 getboolean/getint 转换 |
| os.environb | bytes 键值 | 底层 char** 的字节视图 |

```python
import os

def parse_bool(v):
    return v.strip().lower() in ('1', 'true', 'yes', 'on')

def load(env, dotenv_text='', overrides=None):
    cfg = {'PORT': '8000', 'DEBUG': 'false', 'DB_HOST': 'localhost'}
    for line in dotenv_text.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    for k in list(cfg):
        if k in env:
            cfg[k] = env[k]
    if overrides:
        cfg.update(overrides)
    return {'port': int(cfg['PORT']), 'debug': parse_bool(cfg['DEBUG']),
            'host': cfg['DB_HOST']}

env = {'PORT': '9100'}
dotenv = 'PORT=9000' + chr(10) + 'DEBUG=true' + chr(10)
c = load(env, dotenv, overrides={'DB_HOST': 'prod'})
print('port', c['port'], 'debug', c['debug'], 'host', c['host'])
os.environ['APP_MODE'] = 'prod'
print('env var', os.environ['APP_MODE'])
del os.environ['APP_MODE']
print('bool trap', bool('false'))
```

<OutputBox title='主示例运行结果' output='port 9100 debug True host prod\nenv var prod\nbool trap True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import os\n\ndef parse_bool(v):\n    return v.strip().lower() in (&#39;1&#39;, &#39;true&#39;, &#39;yes&#39;, &#39;on&#39;)\n\ndef load(env, dotenv_text=&#39;&#39;, overrides=None):\n    cfg = {&#39;PORT&#39;: &#39;8000&#39;, &#39;DEBUG&#39;: &#39;false&#39;, &#39;DB_HOST&#39;: &#39;localhost&#39;}\n    for line in dotenv_text.splitlines():\n        line = line.strip()\n        if line and not line.startswith(&#39;#&#39;) and &#39;=&#39; in line:\n            k, v = line.split(&#39;=&#39;, 1)\n            cfg[k.strip()] = v.strip()\n    for k in list(cfg):\n        if k in env:\n            cfg[k] = env[k]\n    if overrides:\n        cfg.update(overrides)\n    return {&#39;port&#39;: int(cfg[&#39;PORT&#39;]), &#39;debug&#39;: parse_bool(cfg[&#39;DEBUG&#39;]),\n            &#39;host&#39;: cfg[&#39;DB_HOST&#39;]}\n\nenv = {&#39;PORT&#39;: &#39;9100&#39;}\ndotenv = &#39;PORT=9000&#39; + chr(10) + &#39;DEBUG=true&#39; + chr(10)\nc = load(env, dotenv, overrides={&#39;DB_HOST&#39;: &#39;prod&#39;})\nprint(&#39;port&#39;, c[&#39;port&#39;], &#39;debug&#39;, c[&#39;debug&#39;], &#39;host&#39;, c[&#39;host&#39;])\nos.environ[&#39;APP_MODE&#39;] = &#39;prod&#39;\nprint(&#39;env var&#39;, os.environ[&#39;APP_MODE&#39;])\ndel os.environ[&#39;APP_MODE&#39;]\nprint(&#39;bool trap&#39;, bool(&#39;false&#39;))' :notes='["导入 os 读取进程环境变量", "定义布尔归一：只认 1/true/yes/on", "模拟 pydantic-settings 的分层加载函数", "默认值层：端口 8000、DEBUG 关、主机 localhost", "逐行解析 .env 文本", "去掉首尾空白", "跳过空行、注释行与无等号行", "按第一个等号拆键值", "用 .env 的值覆盖默认值", "进程环境变量层：只对已知键生效", "env 里有同名键就覆盖上一层", "显式覆盖层：优先级最高", "overrides 最后写入", "把 PORT 转 int、DEBUG 归一 bool，得到类型化配置", "模拟进程环境变量：PORT=9100", "模拟 .env 文件：PORT=9000、DEBUG=true", "按四层加载并覆盖 DB_HOST 为 prod", "PORT 最终取 env 的 9100、DEBUG 取 .env、host 取覆盖", "演示 os.environ 写入后立即生效", "读出刚写入的环境变量", "清理该键，保持环境干净", "揭示 bool(&#39;false&#39;) 为 True 的经典类型陷阱", "密钥用 SecretStr/掩码、托管服务轮换；.env 进 .gitignore、提交 .env.example 占位", "tomllib（3.11+）把 TOML 解析成原生 bool/int；配置漂移靠版本、校验和与启动摘要审计", "十二要素：配置走环境变量与代码分离；os.environ 值全是 str，bool(&#39;False&#39;) 为 True"]' title='第 079 讲 · 配置管理：环境变量、.env 与配置中心' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
class Secret:
    def __init__(self, value):
        self._value = value
    def reveal(self):
        return self._value
    def __str__(self):
        return '***'
    __repr__ = __str__

def load_port(env):
    raw = env.get('PORT', '8000')
    if not raw.isdigit():
        raise ValueError('PORT must be an integer')
    return int(raw)

print('valid port', load_port({'PORT': '8080'}))
try:
    load_port({'PORT': 'eighty'})
except ValueError as e:
    print('startup fails fast', str(e))
token = Secret('sk-live-abc123')
print('log-safe', str(token), 'real', token.reveal())
```

<OutputBox title='对照写法：先自己猜，再点开' output='valid port 8080\nstartup fails fast PORT must be an integer\nlog-safe *** real sk-live-abc123' guess="true" />

`os.environ` 是 `os._Environ`，包装 C 运行时的 environ（`char**` 的 `KEY=VALUE` 串），因此所有值天然是 `str`，没有任何类型元数据；

`bool('False')` 之所以为 `True`，是因为 Python 的真值规则把任意非空字符串判为真，这正是开关配置要写 `parse_bool` 的原因。

`tomllib`（3.11 起）走另一条路：它按 `TOML` 规范把 `false` / `8080` 解析成 `bool` / `int`，与环境变量字符串形成对照。

`pydantic-settings` 的 `BaseSettings` 用元类收集字段别名（环境变量名，默认大小写不敏感），按 init > env > dotenv > secrets > default 求值，再交给 pydantic 做类型校验；

缺必需字段或类型不符在构造对象那一刻抛 `ValidationError`，这就是「启动期失败」的实现机制。

`SecretStr` 通过重写 `__str__` / `__repr__` 返回掩码，避免敏感值被日志格式化函数取到；热更新通常用后台监听加原子替换配置对象，而非就地改字段。

<ConceptDiagram type='compare2' title='第 079 讲 · 十二要素、环境变量与类型陷阱' labels='十二要素、环境变量与类型陷阱|分层覆盖与启动期失败|密钥、轮换与配置漂移' caption='把配置做成可验证、可覆盖、可审计的输入' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 分层覆盖、启动期失败与密钥轮换治理

一份配置通常来自多层，优先级必须显式写清：默认值 < `.env` 文件 < 进程环境变量 < 显式覆盖或 CLI 参数。

`pydantic-settings` 的 `BaseSettings` 把这个顺序定得更细：构造函数的 `init` 参数 > 环境变量 > dotenv 文件 > secrets 目录 > 字段默认值；

字段默认 `case_sensitive=False`，因此环境变量名按大写匹配，可用 `env_prefix` 加前缀、用 `env_nested_delimiter='__'` 读嵌套结构、用 `SettingsConfigDict(env_file='.env')` 指定文件。

它真正的价值是校验：字段带类型与约束，缺必需字段或类型不符会在构造对象时抛 `ValidationError`，于是「启动期失败」而不是等冷门接口首次读取才炸。

工程上把配置收敛成一个类型化、启动后不可变的对象（`dataclass(frozen=True)` 或 `BaseSettings` 实例），全模块只从它读；

启动时全量校验并打印一份非敏感字段摘要，任何缺失或越界都立刻退出进程。

密钥绝不硬编码、绝不提交仓库：生产环境交给托管服务（Vault、AWS Secrets Manager、K8s Secret）并支持轮换与热更新，轮换不该触发全量发版。

日志与异常里也要防泄漏：本讲对照示例里自定义了一个包装类，重写 `__str__` / `__repr__` 只返回掩码（可验证 `str(token)` 得到 `'***'`，只有 `reveal()` 才给真值）；

Pydantic 的 `SecretStr` 是同一思路的现成类型，取值方法是 `get_secret_value()`。

默认不把完整请求体或响应写进日志。配置漂移指同一份配置在不同环境、或不同时间悄悄不一致：对策是给类型化配置对象加版本号与校验和、坚持单一事实源、按环境分层覆盖（`dev` / `staging` / `prod` 前缀或独立文件）、每个键标注 owner 与默认值，并对每次变更留审计记录。

启动时把一份非敏感的配置摘要快照进日志，线上就能回答「这次行为变化是不是配置改了」。把校验、分层与脱敏收进一个 `Config` 类，比散落在各处的 `os.getenv` 可靠得多。


## 类型化不可变配置与启动期校验

把散落各处的 `os.getenv` 收敛成一个 `Config` 对象：按默认值、`.env`、进程环境、显式覆盖四层合并，逐字段做类型转换与范围校验，越界立刻抛 `ValueError` 让进程起不来，公开视图只暴露非敏感字段。这样配置错误在启动瞬间暴露，密钥也不会出现在 `public()` 里。

下面片段用标准库实现这套装载器，演示合法配置、端口越界被拒、以及密钥不进公开摘要三条契约，真实项目把校验换成 `pydantic-settings` 即可获得同样的启动期失败语义。

```python
import json

DEFAULTS = {'PORT': '8000', 'DEBUG': 'false', 'WORKERS': '4'}

def coerce_bool(v):
    return v.strip().lower() in ('1', 'true', 'yes', 'on')

class Config:
    def __init__(self, env, dotenv=None, overrides=None):
        merged = dict(DEFAULTS)
        if dotenv:
            merged.update(dotenv)
        merged.update({k: v for k, v in env.items() if k in merged})
        if overrides:
            merged.update(overrides)
        self.port = int(merged['PORT'])
        self.debug = coerce_bool(merged['DEBUG'])
        self.workers = int(merged['WORKERS'])
        if self.port < 1 or self.port > 65535:
            raise ValueError('PORT out of range')
    def public(self):
        return {'port': self.port, 'debug': self.debug, 'workers': self.workers}

env = {'PORT': '9200'}
dotenv = {'DEBUG': 'true'}
cfg = Config(env, dotenv, overrides={'WORKERS': '8'})
print('config', json.dumps(cfg.public(), sort_keys=True))
try:
    Config({'PORT': '70000'})
except ValueError as e:
    print('startup rejected', str(e))
print('secret never in public', 'SECRET' not in cfg.public())
```

<Callout type="idea" title='落地提示' text='用类型化配置对象、启动时全量校验、按环境分层覆盖，生产密钥交给托管服务并支持热更新' />


## 练习、自测与一页纸速记

<Exercise title='基础：验证环境变量全是字符串并显式转型' task='写入 DEMO_N=&#39;5&#39;，打印 os.getenv、int 转型结果，并揭示 bool(&#39;False&#39;) 为真。' solution='import os\nos.environ[&#39;DEMO_N&#39;] = &#39;5&#39;\nprint(&#39;getenv&#39;, os.getenv(&#39;DEMO_N&#39;), &#39;cast&#39;, int(os.environ[&#39;DEMO_N&#39;]) * 2)\nprint(&#39;bool trap&#39;, bool(&#39;False&#39;))\ndel os.environ[&#39;DEMO_N&#39;]' explain='环境变量底层是字符串，端口要 int() 转、开关要 parse_bool；bool(&#39;False&#39;) 为 True 是典型误用，转型必须在读取处显式完成。' />

<Exercise title='进阶：实现两层覆盖' task='默认值 PORT=8000，进程环境 PORT=9000，打印合并后的端口，说明覆盖优先级。' solution='defaults = {&#39;PORT&#39;: &#39;8000&#39;}\nenv = {&#39;PORT&#39;: &#39;9000&#39;}\ncfg = dict(defaults)\ncfg.update(env)\nprint(&#39;port&#39;, cfg[&#39;PORT&#39;])' explain='dict.update 表达「高优先级层覆盖低优先级层」；真实配置里顺序是默认值 &lt; .env &lt; 环境变量 &lt; 显式覆盖，且每步都要类型转换。' />

<Quiz no='079-1' q='关于 os.environ 的值类型，正确的是？' :options='["全部是 str，端口/开关必须显式转型", "自动推断为 int / bool", "是 bytes", "缺键时返回 None 且类型为空"]' answer="0" explain='os.environ 包装 C 的 char** 键值串，没有类型；int(...) 与 parse_bool 必须自己写，bool(&#39;False&#39;) 会得到 True。' />

<Quiz no='079-2' q='配置错误最合理的暴露时机是？' :options='["启动期全量校验，失败立即退出", "第一次读到该配置的冷门接口里", "每天定时巡检时", "用户报错后再回滚"]' answer="0" explain='把配置收敛成类型化对象并在构造时校验（pydantic-settings 的 ValidationError），错误就不会流到运行期某个分支才炸。' />

<Quiz no='079-3' q='pydantic-settings 里环境变量与 .env 的优先级是？' :options='["进程环境变量高于 .env，init 参数最高", ".env 永远最高", "默认值最高", "按字母序决定"]' answer="0" explain='顺序是 init 参数 &gt; 环境变量 &gt; dotenv &gt; secrets &gt; 字段默认值；显式部署注入能盖住文件里的值，便于按环境分层覆盖。' />

<Predict no='079-4' q='执行 bool(&#39;False&#39;) 的输出是？' :options='["True", "False", "TypeError"]' answer='0' output='True' explain='Python 的真值规则把任意非空字符串判为真，&#39;False&#39; 长度为 6 显然非空；开关配置必须写 parse_bool 或交给类型化配置对象校验，不能用 bool() 直接转。' />

<FillBlank no='079-5' tpl='___ os' :answers='["import"]' hint='回想本讲关于 十二要素与环境变量 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 十二要素、环境变量与类型陷阱 的落点。' />

<KnowledgeCard :points='["十二要素：配置走环境变量与代码分离；os.environ 值全是 str，bool(&#39;False&#39;) 为 True", "覆盖优先级：默认值 &lt; .env &lt; 进程环境变量 &lt; 显式覆盖/CLI；pydantic-settings 为 init &gt; env &gt; dotenv &gt; secrets &gt; default", "pydantic-settings BaseSettings 默认 case_sensitive=False，支持 env_prefix / env_nested_delimiter=&#39;__&#39;", "启动期全量校验抛 ValidationError，类型化不可变配置对象是单一事实源", "密钥用 SecretStr/掩码、托管服务轮换；.env 进 .gitignore、提交 .env.example 占位", "tomllib（3.11+）把 TOML 解析成原生 bool/int；配置漂移靠版本、校验和与启动摘要审计"]' :pitfalls='["用 bool(os.environ[&#39;DEBUG&#39;]) 解析开关", "硬编码密钥或把 .env 提交进仓库", "配置错误等运行期冷门分支才暴露", "把密钥硬编码或提交进仓库，轮换时只能全量改代码重新发版"]' summary='配置错误应该在启动瞬间失败，而不是等某个冷门接口第一次读到空字符串才炸' />

1. 十二要素：配置走环境变量与代码分离；os.environ 值全是 str，bool('False') 为 True

2. 覆盖优先级：默认值 < .env < 进程环境变量 < 显式覆盖/CLI；pydantic-settings 为 init > env > dotenv > secrets > default

3. pydantic-settings BaseSettings 默认 case_sensitive=False，支持 env_prefix / env_nested_delimiter='__'

[下一讲：打包与发布：pyproject、wheel 与 PyPI](/engineering/packaging)
