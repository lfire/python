---
title: 办公自动化进阶：PPT、GUI 与批处理
description: 用 python-pptx 生成与复用模板、dotenv 隔离密钥、Tkinter 最小界面与后台线程、Pillow 与二维码、moviepy 分段拼接、批处理事务性与 NFC 路径及打包要点。
---

# 办公自动化进阶：PPT、GUI 与批处理

124 讲把邮件、PDF、Excel、Word 自动化了一遍，可还有三类活儿没落地：每周重做的汇报 PPT、发给不会敲命令的同事用的小工具、以及一批图片加水印转码和几十段视频的拼接加音轨。它们不像前面那样读写一个文件就收工，而要处理模板、界面线程、媒体编码、批量失败隔离与交付打包。这一篇按一条流水线的顺序展开：先用 `python-pptx` 认清版式与占位符，把 JSON 映射成一页页幻灯片并复用模板；再用 `dotenv` 把密钥与路径挪出代码；随后做一个 Tkinter 最小 GUI，讲清后台线程为何不能碰控件；接着用 `Pillow` 处理图片与二维码、用 `moviepy` 分段拼接加音轨；最后收在批处理事务性、文件名 NFC 规范化、跨平台路径与打包注意点。示例都能在本机跑，媒体与界面另给无显示环境的替代做法。

## python-pptx 的版式、占位符与形状

`python-pptx` 操作的是 PowerPoint 文件本身，不是去模拟鼠标点击。一份演示文稿由母版、版式、幻灯片三层构成：母版定字体与配色，版式定这一页有哪些坑位，幻灯片才是往坑位里填内容。新建 `Presentation()` 会拿到一份自带若干标准版式的空白文稿，`slide_layouts[i]` 取出第 `i` 个版式，`slides.add_slide(layout)` 按它加一页。页面上带虚线框、提示「单击此处添加标题」的那一块就是占位符，用 `slide.shapes.title` 或 `slide.placeholders[idx]` 访问；`add_textbox`、`add_picture`、`add_table` 则用来加不在版式里的自由元素。所有尺寸单位是 EMU，写 `Inches(2)`、`Pt(14)` 比直接写整数可读得多。

| 对象 / 方法 | 作用 | 常见误用 |
| --- | --- | --- |
| `Presentation()` | 新建空文稿 | 想复用自定义母版却没传模板路径 |
| `Presentation('tpl.pptx')` | 载入模板 | 模板里已有的页也会一起带进来 |
| `prs.slide_layouts[i]` | 取第 `i` 个版式 | 索引含义随模板变化，别凭记忆写死 |
| `slides.add_slide(layout)` | 新增一页 | 不传版式会直接报错 |
| `slide.shapes.title` | 标题占位符 | 无标题版式上取到 `None` |
| `slide.placeholders[idx]` | 按索引取占位符 | `idx` 要先打印核对再填 |
| `shapes.add_textbox(...)` | 自由文本框 | 尺寸用 `Inches` / `Pt`，别写裸整数 |
| `prs.save(path)` | 写出文件 | 覆盖同名文件不提示，先备份 |

### 母版、版式与占位符索引

默认模板的版式索引有惯例，但换一份公司模板就全变了，所以第一次接手模板时先跑一段「打印每个版式的名字和占位符」的探查代码，再决定映射关系。

| 版式索引 | 名称 | 占位符 |
| --- | --- | --- |
| 0 | Title Slide | 0 标题、1 副标题 |
| 1 | Title and Content | 0 标题、1 正文 |
| 2 | Section Header | 0 标题、1 正文 |
| 5 | Title Only | 0 标题 |
| 6 | Blank | 无占位符，全靠 `add_*` 自己摆 |

用到 `python-pptx`，安装命令见下方。

```bash
pip install python-pptx
```

下面生成两页：标题页填标题与副标题，内容页填带层级的要点，再补一个自由文本框。

```python
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()

title_slide = prs.slides.add_slide(prs.slide_layouts[0])
title_slide.shapes.title.text = '季度汇报'
title_slide.placeholders[1].text = '数据组 · 2026 Q1'

content = prs.slides.add_slide(prs.slide_layouts[1])
content.shapes.title.text = '本季要点'
frame = content.placeholders[1].text_frame
frame.text = '营收同比增长'
second = frame.add_paragraph()
second.text = '新增三个客户'
second.level = 1

box = content.shapes.add_textbox(Inches(1), Inches(5.2), Inches(6), Inches(0.8))
run = box.text_frame.paragraphs[0].add_run()
run.text = '由脚本生成'
run.font.size = Pt(12)
run.font.name = 'Microsoft YaHei'

prs.save('demo.pptx')
print('已生成页数', len(prs.slides))
```

`run.font.name` 这行别省：不指定字体时，中文在没装默认字体的机器上会渲染成方框，这一点在后面的常见坑里还会展开。

## 把 JSON 数据映射成一页页幻灯片

会填一页之后，真正的效率来自把「内容」和「排版」分开：内容是一份结构化数据（JSON 或 YAML），排版是一段固定的映射代码。每条记录描述用哪个版式、标题是什么、要点有哪些、要不要插图；生成器遍历记录，逐页套版式填值。这样换一批数据只是换 JSON，汇报的版式、字体、配色都不动。字段最好都给缺省值——某条记录没写 `bullets` 就跳过要点，没写 `image` 就不插图，别让一条缺字段的数据把整批生成中断。

| JSON 字段 | 落到幻灯片哪里 | 缺省处理 |
| --- | --- | --- |
| `layout` | `slide_layouts[layout]` | 默认取 1 |
| `title` | `shapes.title.text` | 留空字符串 |
| `bullets` | 正文占位符逐段 `add_paragraph` | 空列表跳过 |
| `image` | `shapes.add_picture` | 不插图 |
| `notes` | 备注页 `notes_slide` | 不写 |

### 用一份模板复用字体与配色

更进一步是把公司模板存成 `template.pptx`，生成器用 `Presentation('template.pptx')` 载入，页面自动继承母版里的 logo、字体和主题色。注意载入模板会把它已有的幻灯片也带进来，所以模板里只放母版与版式，不要留示例页。下面这段沿用 `python-pptx`，安装命令 `pip install python-pptx`，先把一份空模板存盘，再从 JSON 字符串解析出两页内容并复用它。

```python
import json
from pptx import Presentation

# 只含母版与版式的空模板
Presentation().save('template.pptx')

RAW = '''[
  {"layout": 1, "title": "第一页", "bullets": ["营收 +12%", "新增 3 个客户"]},
  {"layout": 1, "title": "第二页", "bullets": ["成本下降", "复购率持平"]}
]'''


def build(spec, template='template.pptx'):
    prs = Presentation(template)
    for item in spec:
        slide = prs.slides.add_slide(prs.slide_layouts[item.get('layout', 1)])
        if slide.shapes.title:
            slide.shapes.title.text = item.get('title', '')
        frame = slide.placeholders[1].text_frame
        frame.clear()
        for i, line in enumerate(item.get('bullets', [])):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.text = line
            para.level = 0
    return prs


deck = build(json.loads(RAW))
deck.save('report.pptx')
print('从 JSON 生成页数', len(deck.slides))
```

`frame.clear()` 会清掉占位符里原有的示例文字并留一个空段落，之后第一段复用 `paragraphs[0]`、其余用 `add_paragraph()`，这样不会多出一行空白项目符号。

## dotenv 把密钥与路径挪出代码

脚本一旦要发邮件、调接口、读公司模板，就会遇上 token、密码、内网域名这些不能写死的东西。硬编码的代价不止是泄露：换个环境就得改源码、重新打包。`python-dotenv` 的做法是把键值放在项目根目录的 `.env` 文件里，代码用 `os.getenv` 读；仓库里只提交一个只有键名、没有值的 `.env.example`，并把 `.env` 写进 `.gitignore`。这样「配置和代码」彻底分开，本机、CI、同事机器各放各的 `.env`。

| 配置项 | 放哪 | 原因 |
| --- | --- | --- |
| token、密码 | `.env`，不入库 | 一旦提交进历史，轮换都来不及 |
| 域名、输出目录 | `.env` 或配置文件 | 开发、预发、生产各不相同 |
| 模板路径 | 配置或 `Path` 相对定位 | 打包后绝对路径会失效 |
| 调试开关 | 环境变量 | 不改代码就能切行为 |
| 键名示例 | `.env.example` | 只放键名，供同事复制填空 |

用到 `python-dotenv`，安装命令见下方。

```bash
pip install python-dotenv
```

下面在临时目录写一个 `.env` 再读回来，演示 `override=True` 与带默认值的 `getenv`。

```python
import os
import tempfile
from dotenv import load_dotenv

folder = tempfile.mkdtemp()
env_path = os.path.join(folder, '.env')
with open(env_path, 'w', encoding='utf-8') as f:
    f.write('SMTP_TOKEN=abc123\nOUTPUT_DIR=./out\nDEBUG=0\n')

load_dotenv(env_path, override=True)
token = os.environ['SMTP_TOKEN']
debug = os.getenv('DEBUG', '0') == '1'
print('token 长度', len(token), 'debug', debug,
      '输出目录', os.getenv('OUTPUT_DIR', './default'))
```

`os.environ['SMTP_TOKEN']` 在缺键时直接抛 `KeyError`，适合「缺了就别跑」的必填项；`os.getenv` 带默认值，适合可选开关。`load_dotenv` 默认不覆盖已有环境变量，CI 里注入的值优先，本地想强制覆盖才加 `override=True`。

## Tkinter 最小界面与后台线程

不是每个同事都愿意开终端。Tkinter 在标准库里，`tk.Tk()` 建窗口，`Label` 显示文字，`Button` 绑一个回调函数，`mainloop()` 进入事件循环，几行就能把脚本包成能点的小工具。真正的坎在于：主线程被 `mainloop` 占着，一旦在回调里跑耗时任务（批量转图、生成几十页 PPT），窗口就会假死、转圈、点不动。解法是把耗时工作丢进 `threading.Thread`，但 Tkinter 的控件**只能**由创建它的主线程更新——工作线程直接调 `label.config(...)` 轻则无响应、重则崩溃。

### 为什么工作线程不能碰控件

稳妥的桥是 `queue.Queue` 加 `after()`：工作线程只计算、把结果 `put` 进队列；主线程用 `root.after(50, poll)` 定时轮询，`get_nowait()` 取到结果后在主线程里更新控件。这样界面全程可响应，线程边界也干净。下面给最小可运行骨架。

```python
import queue
import threading
import time
import tkinter as tk


def heavy(n):
    time.sleep(0.1)
    return n * n


def on_click():
    box = queue.Queue()

    def worker():
        box.put(heavy(21))

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            value = box.get_nowait()
        except queue.Empty:
            root.after(50, poll)
        else:
            label.config(text='结果：{}'.format(value))

    poll()


root = tk.Tk()
root.title('最小 GUI')
label = tk.Label(root, text='等待计算')
label.pack(padx=30, pady=10)
tk.Button(root, text='开始', command=on_click).pack(pady=10)
root.mainloop()
```

<Callout type='tip' title='线程规则' text='工作线程只负责计算并把结果放进队列，控件更新一律回到主线程执行' />

无界面环境（CI、纯服务器）里 `tk.Tk()` 会抛 `TclError` 说找不到 display，替代做法是给这套逻辑留一个纯函数入口：把 `heavy` 和批处理单独做成命令行可调用的模块，GUI 只是薄薄一层壳；真要在无显示机器上跑界面测试，用 `xvfb-run python app.py` 提供虚拟显示即可。

## Pillow 图片处理与二维码合成

批量给封面图加水印、缩略图、贴二维码，是办公脚本的高频需求。`Pillow` 用 `Image.new` 造画布、`ImageDraw` 画框和文字、`paste` 叠加、`thumbnail` 缩放；二维码交给 `qrcode`，`make(...).save(path)` 直接出 PNG，再用 `Image.open` 读回来贴到画布上。全程可以只用内存生成的对象，不必准备素材图，所以这段脚本在空目录里也能跑通。

用到 `Pillow` 与 `qrcode`，安装命令见下方。

```bash
pip install Pillow qrcode
```

```python
from PIL import Image, ImageDraw
import qrcode

card = Image.new('RGB', (320, 200), 'white')
draw = ImageDraw.Draw(card)
draw.rectangle([10, 10, 310, 190], outline='gray', width=2)
draw.text((20, 20), 'Report 2026', fill='black')

qrcode.make('https://example.com/report').save('qr_tmp.png')
qr = Image.open('qr_tmp.png').convert('RGB').resize((120, 120))
card.paste(qr, (180, 60))
card.save('card.png')

thumb = card.copy()
thumb.thumbnail((160, 100))
thumb.save('card_thumb.png')
print('原图', card.size, '缩略图', thumb.size)
```

`thumbnail` 是原地缩放且保持比例，和 `resize` 的「拉伸到指定尺寸」不同；要保留原图再生成缩略图，记得先 `copy()`。二维码内容别直接拼敏感参数，链接里带 token 时和 `.env` 一个道理，先想清楚谁会扫到这张图。

## moviepy 分段、拼接与加音轨

视频侧的需求通常是「从几段素材各取一段、按序拼起来、再压一条背景音」。moviepy 用 `ColorClip` 一类对象表示片段，`subclipped(a, b)` 截取区间，`concatenate_videoclips` 按序拼接，`with_audio` 挂音轨，最后 `write_videofile` 编码输出。音轨可以由 numpy 数组直接构造 `AudioArrayClip`，不依赖外部音频文件。编码这一步需要 ffmpeg：imageio-ffmpeg 会自动带一个二进制，首次使用可能需要联网取回，离线机器上要预先装好系统 ffmpeg。

用到 `moviepy` 与 numpy，安装命令见下方；示例按 2.x 的 API 写。

```bash
pip install "moviepy>=2.0" numpy
```

```python
import numpy as np
from moviepy import AudioArrayClip, ColorClip, concatenate_videoclips


def clip(color, seconds):
    return ColorClip(size=(320, 240), color=color).with_duration(seconds).with_fps(24)


head = clip((200, 40, 40), 1)
middle = clip((30, 30, 30), 2)
tail = clip((40, 80, 200), 1)

# 分段：中间只取 0.5 到 1.5 秒，再拼接
merged = concatenate_videoclips([head, middle.subclipped(0.5, 1.5), tail])

fps = 44100
t = np.linspace(0, merged.duration, int(merged.duration * fps), endpoint=False)
wave = 0.2 * np.sin(2 * np.pi * 440 * t)
audio = AudioArrayClip(np.column_stack([wave, wave]), fps=fps)
final = merged.with_audio(audio)

try:
    final.write_videofile('out.mp4', codec='libx264', audio_codec='aac', fps=24)
    print('已写出 out.mp4，时长', final.duration)
except Exception as exc:
    print('本机缺 ffmpeg，分段与音轨已在内存构建；时长', final.duration,
          '原因', type(exc).__name__)
```

1.x 版本里这些方法是 `subclip`、`set_audio`，迁移时最容易在这里卡住。没有素材、也没有 ffmpeg 的机器上，把 `write_videofile` 换成逐帧导出 PNG 再交给系统工具合成，或直接跳过编码只验证 `final.duration` 与拼接顺序，脚本同样能跑。

## 批处理任务的事务性与错误隔离

一次处理几百个文件时，「整批中断」和「留下半截文件」是最烦的两件事。事务性的要点是：每条任务先把产物写进临时区，确认成功后再用 `os.replace` 原子挪进正式目录；失败就只记一笔，继续下一条。错误隔离靠逐条 `try/except`，把失败清单连同异常类型一起返回，跑完统一打印，绝不因为一条坏数据丢掉其余成果。再往前一步是幂等：输出前先看目标是否已存在，或维护一份 manifest，重跑时跳过已完成项。

| 现象 | 根因 | 隔离动作 |
| --- | --- | --- |
| 一条失败整批中断 | 循环里没有逐条捕获 | 每条 `try/except`，记录后继续 |
| 输出目录留半截文件 | 直接写正式路径 | 先写临时区，成功再 `os.replace` |
| 重跑重复处理 | 没有完成标记 | 查目标是否存在，维护 manifest |
| 中文名找不到文件 | macOS 的 NFD 与 NFC 不一致 | `unicodedata.normalize('NFC', name)` |
| Windows 上路径报错 | 手写反斜杠拼接 | 用 `pathlib` 或 `os.path.join` |

下面只用标准库演示这套流程，`b.txt` 被故意设成失败项，其余两条照常产出。

```python
import os
import shutil
import tempfile


def process_one(src, tmp_dir):
    if os.path.basename(src) == 'b.txt':
        raise ValueError('模拟单条失败')
    out = os.path.join(tmp_dir, os.path.basename(src) + '.done')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('ok')
    return out


def run_batch(files, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    tmp = dst_dir + '.tmp'
    os.makedirs(tmp, exist_ok=True)
    ok, failed = [], []
    for src in files:
        try:
            produced = process_one(src, tmp)
            target = os.path.join(dst_dir, os.path.basename(produced))
            os.replace(produced, target)
            ok.append(os.path.basename(src))
        except Exception as exc:
            failed.append((os.path.basename(src), type(exc).__name__))
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, failed


src = tempfile.mkdtemp()
names = ['a.txt', 'b.txt', 'c.txt']
for n in names:
    open(os.path.join(src, n), 'w', encoding='utf-8').close()
files = [os.path.join(src, n) for n in names]
ok, failed = run_batch(files, src + '_out')
print('成功', ok, '失败', failed)
print('产物', sorted(os.listdir(src + '_out')))
```

`os.replace` 在同一文件系统内是原子操作，要么看到完整产物、要么看不到，不会留下写了一半的文件；跨盘时才需要退化成复制加删除。临时目录用 `shutil.rmtree(..., ignore_errors=True)` 收尾，保证上一轮的残骸不带到下一轮。

## 文件命名 NFC 规范化与跨平台路径

同一个带重音的字，Unicode 有两种写法：é 可以是一个预组合字符（NFC），也可以是 e 加一个组合重音（NFD）。macOS 的文件系统倾向存 NFD，Linux 与 Windows 多是 NFC，于是「看起来一模一样」的两个文件名，用字符串直接比较却不等，脚本按名字找文件就莫名失败。修法很机械：所有从外部拿到的文件名先过一遍 `unicodedata.normalize('NFC', name)`，再比较、再拼路径。路径本身别用反斜杠字符串拼接，`pathlib.Path` 或 `os.path.join` 会按当前系统选分隔符，`Path.parts`、`suffix`、`name` 也比手写切片稳。

```python
import unicodedata
from pathlib import Path

names = ['cafe\u0301.txt', 'caf\u00e9.txt']
normalized = [unicodedata.normalize('NFC', n) for n in names]
print('原始是否相等', names[0] == names[1])
print('规范化后是否相等', normalized[0] == normalized[1])
print('规范化列表', normalized)

target = Path.home() / 'reports' / '2026' / normalized[0]
print('拼接结果', target)
print('末两级', target.parts[-2:])
print('文件名', target.name, '后缀', target.suffix)
```

`Path.home()` 在不同系统指向各自的用户目录，配合 `/` 运算符比 `os.path.join` 更紧凑；真正要落地时用 `target.parent.mkdir(parents=True, exist_ok=True)` 先把目录建出来。

## 打包成可执行文件的注意点

把脚本交给同事，最省事是 PyInstaller 打成一个 exe 或 app。难点几乎都不在打包命令，而在「运行时路径变了」：单文件模式下资源被解压到临时目录，`__file__` 指向的是解压路径，写死的 `./template.pptx` 会找不到。附带的模板、字体、图片要用 `--add-data` 显式带上，代码里通过 `sys._MEIPASS` 或 `importlib.resources` 定位，而不是相对当前工作目录。另外，动态导入的模块（插件、`importlib.import_module`）PyInstaller 常常分析不到，得用 `--hidden-import` 补。

| 事项 | 做法 | 说明 |
| --- | --- | --- |
| 单文件 | `-F` | 启动略慢，资源先解压到临时目录 |
| 附带模板、字体、图片 | `--add-data` | 运行时用 `sys._MEIPASS` 或 `importlib.resources` 定位 |
| 动态导入漏包 | `--hidden-import` | 插件式导入常需手动补 |
| 体积偏大 | 干净虚拟环境里只装必要依赖 | 别把整个数据科学栈打进去 |
| 跨平台 | 各目标平台各打一次 | macOS 上产不出 Windows 的 exe |
| 密钥文件 | 排除在打包清单外 | `.env` 不该被打进可执行文件 |

命令示例：`pyinstaller -F --add-data "template.pptx;." app.py`，Windows 用分号、macOS 与 Linux 用冒号分隔目标路径，写 CI 脚本时别混用。

```bash
pip install pyinstaller
pyinstaller -F --add-data "template.pptx;." app.py
```

## 常见坑 / 边界

1. **中文字体缺失，打开是方框或乱码**：`python-pptx` 与 `Pillow` 都不带字体，目标机没装对应字体就渲染失败。修复：显式设 `run.font.name`（如 `Microsoft YaHei`）、`ImageDraw` 指定 `truetype` 字体文件，并确认目标机有同款字体或随包附带。
2. **Tkinter 工作线程直接更新控件**：界面假死甚至崩溃。修复：工作线程只往 `queue.Queue` 放结果，主线程用 `after` 轮询后调用 `config`，控件操作一律留在主线程。
3. **macOS 文件名 NFD 导致查找失败**：视觉相同的名字字符串比较却不等。修复：所有外部文件名先 `unicodedata.normalize('NFC', name)`，再比较与拼接路径。
4. **手写字串拼路径、用反斜杠分隔**：Windows 上报路径错或转义被吃掉。修复：改用 `pathlib.Path` 的 `/` 运算符或 `os.path.join`，需要建目录时配 `mkdir(parents=True, exist_ok=True)`。
5. **打包后资源与 `.env` 处理失当**：`__file__` 相对路径失效，密钥被打进包。修复：资源走 `sys._MEIPASS` 或 `importlib.resources`，`.env` 排除在打包清单外并写进 `.gitignore`，仓库只留 `.env.example`。

## 两道练习

::: details 练习 1 · 从 .env 读模板路径生成一页
写出参考解：从 `.env` 读取 `TEMPLATE` 与 `REPORT_TITLE`，载入模板、加一页只含标题的版式并保存。用到 `python-dotenv` 与 `python-pptx`，安装命令 `pip install python-dotenv python-pptx`。

```python
# 参考解
import os
from dotenv import load_dotenv
from pptx import Presentation

load_dotenv()
path = os.getenv('TEMPLATE', 'template.pptx')
prs = Presentation(path)
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = os.getenv('REPORT_TITLE', '未命名')
prs.save('one.pptx')
print('已生成', len(prs.slides), '页')
```
:::

::: details 练习 2 · 批量写文件时隔离单条失败
给一批文件名逐条写入内容，要求某一条抛错不影响其余条目，并分别返回成功清单与失败清单。只用标准库，写出参考解。

```python
# 参考解
import os
import tempfile


def write_one(path, payload):
    if 'bad' in os.path.basename(path):
        raise ValueError('模拟单条失败')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(payload)


def batch(names, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ok, bad = [], []
    for name in names:
        try:
            write_one(os.path.join(out_dir, name), 'data')
            ok.append(name)
        except Exception as exc:
            bad.append((name, type(exc).__name__))
    return ok, bad


print(batch(['a.txt', 'bad.txt', 'c.txt'], tempfile.mkdtemp()))
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/office-advanced.py`

```bash
python3 examples/topics/office-advanced.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/office-advanced.py) · [全部示例代码索引](/examples/)
