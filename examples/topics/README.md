# 专题补遗示例文件

本目录把 [专题补遗](../../docs/topics/index.md) 各篇正文里出现的 Python 代码整理成可独立运行的示例文件，供 clone 仓库后直接执行。每个文件与一篇专题页一一对应，代码按源文 `python` 代码块的出现顺序排列，段前注释标明对应章节与演示内容。完整背景见 [示例代码索引](../../docs/examples/index.md)。

## 对应关系一览

| 专题页 | 示例文件 | 主要依赖 | 纯净环境可跑部分 |
| --- | --- | --- | --- |
| [regex](../../docs/topics/regex.md) | `regex.py` | 标准库 `re`；可选第三方 `regex` | 绝大多数段：编译、匹配、分组、替换、回溯与超时思路 |
| [scrapy-antibot](../../docs/topics/scrapy-antibot.md) | `scrapy-antibot.py` | `scrapy`、`itemadapter`、`scrapyd`、`scrapyd-client` | `sqlite3` 去重管道、随机 UA、日志与请求指纹等标准库段 |
| [testing-automation](../../docs/topics/testing-automation.md) | `testing-automation.py` | `pytest`、`requests`、`PyYAML`、`selenium` | `http.server` 打桩、`csv`/`json`/`xml` 解析、`unittest.mock` 段 |
| [office-advanced](../../docs/topics/office-advanced.md) | `office-advanced.py` | `python-pptx`、`python-dotenv` | 队列与线程并发、JSON 解析、`tempfile` 等标准库段；PPT 生成需 python-pptx |
| [dl-projects](../../docs/topics/dl-projects.md) | `dl-projects.py` | `torch`、`torchvision` | 纯 Python 的张量运算、梯度与训练循环原理段（`random`/`math`） |
| [rag-frameworks](../../docs/topics/rag-frameworks.md) | `rag-frameworks.py` | `llama-index` 系列、`pypdf`、`openai`、`httpx`、`python-dotenv` | 余弦相似度、文本分块、纯 JSON 向量检索等标准库段 |
| [web-frameworks](../../docs/topics/web-frameworks.md) | `web-frameworks.py` | `Flask`、`Flask-SQLAlchemy`、`gunicorn`、`pytest` | `secrets` 等标准库辅助段；路由与请求响应段需 Flask |
| [data-projects](../../docs/topics/data-projects.md) | `data-projects.py` | `pandas`、`numpy`、`scipy`、`seaborn`、`matplotlib` | 标准库 `csv` 等价管道、`csv` 灌 `sqlite3` 查询工具、练习 1 住院次均 |
| [toolchain-foundation](../../docs/topics/toolchain-foundation.md) | `toolchain-foundation.py` | 几乎全标准库（`pathlib`/`sqlite3`/`sysconfig`/`re` 等）；可选 `requests`、`flask` | 几乎全部：文件遍历、权限位、glob 匹配、sqlite、解释器环境探测 |

## 统一运行命令

在仓库根目录执行：

```bash
python3 examples/topics/<slug>.py
```

例如本目录已提供的示例：

```bash
python3 examples/topics/data-projects.py
```

## 依赖安装（按专题分组）

依赖都是可选的，按需安装对应专题即可，不必一次装齐：

```bash
# regex（标准库 re 已够用，regex 为可选增强）
python3 -m pip install regex

# scrapy-antibot
python3 -m pip install scrapy scrapyd scrapyd-client

# testing-automation
python3 -m pip install pytest requests PyYAML selenium

# office-advanced
python3 -m pip install python-pptx python-dotenv

# dl-projects
python3 -m pip install torch torchvision

# rag-frameworks
python3 -m pip install llama-index llama-index-embeddings-huggingface pypdf openai httpx python-dotenv

# web-frameworks
python3 -m pip install Flask Flask-SQLAlchemy gunicorn pytest

# data-projects
python3 -m pip install pandas numpy scipy seaborn matplotlib
python3 -m pip install nbconvert weasyprint   # 需要把 Notebook 或 HTML 转成 PDF 时再装

# toolchain-foundation
python3 -m pip install requests flask   # 正文示例用到，核心段无需安装
```

## 不装任何库也能跑通

每个示例文件里，需要第三方库的片段都用 `try: import ... except ImportError: print("跳过：需要 pip install xxx")` 包成可选段。**缺库时该段会自动跳过并打印提示，不会抛 Traceback**，因此纯净环境（不装任何第三方库）也能跑通全部标准库片段并看到结果，进程返回码为 0。

配套的可运行性约定：绘图使用 `Agg` 后端只写文件、不弹图形窗口；导出与图片都写入 `tempfile.TemporaryDirectory()` 临时目录并自动清理，不改动仓库里已有文件；不访问外网、不使用 `input()` 或无限循环。

## 专题 slug 清单

共 9 篇专题有独立示例文件：

- `regex`
- `scrapy-antibot`
- `testing-automation`
- `office-advanced`
- `dl-projects`
- `rag-frameworks`
- `web-frameworks`
- `data-projects`
- `toolchain-foundation`

`reference-map` 是各讲知识点与专题的对照索引页，只做导航、不含独立示例代码，因此没有对应的 `.py` 文件。

## 相关链接

- [示例代码索引](../../docs/examples/index.md)
- [专题补遗](../../docs/topics/index.md)
