"""office-advanced 专题示例：办公自动化进阶：PPT、GUI 与批处理

对应课程页：/topics/office-advanced
GitHub 源文件：https://github.com/lfire/python/blob/main/examples/topics/office-advanced.py

依赖安装（可选，第三方段缺库时会自动跳过）：
    python3 -m pip install python-pptx python-dotenv Pillow qrcode 'moviepy>=2.0' numpy
    # tkinter 属于标准库，无图形环境时该段只保留定义、不创建窗口

运行命令：
    python3 examples/topics/office-advanced.py

说明：本文件按源专题 tools/course/topics/office-advanced.md 中 python 代码块的出现顺序整理。
标准库段（批处理事务性、NFC 规范化、os.replace 原子写、pathlib 路径、队列与线程）
在纯净环境直接跑出结果；用到 python-pptx / python-dotenv / Pillow / qrcode / moviepy /
numpy 的段用 try/except 包成可选段，缺库时打印跳过提示。所有产物（pptx、png、env、
批量文件）都写入 tempfile.TemporaryDirectory() 自动清理，不改动仓库里已有文件；
不弹 GUI 窗口、不启浏览器、不访问外网，也不实际编码视频，不使用交互式输入或无限循环。
"""


# ===== 01 · 源文节 python-pptx 的版式、占位符与形状 · 演示 标题页/内容页占位符、层级要点、自由文本框与字号字体 =====
def demo_01_pptx_basics():
    try:
        import os
        import tempfile
        from pptx import Presentation
        from pptx.util import Inches, Pt

        with tempfile.TemporaryDirectory() as td:
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

            prs.save(os.path.join(td, 'demo.pptx'))
            print('已生成页数', len(prs.slides))
    except ImportError:
        print('跳过：需要 pip install python-pptx')


demo_01_pptx_basics()


# ===== 02 · 源文节 把 JSON 数据映射成一页页幻灯片 / 用一份模板复用字体与配色 · 演示 空模板、json.loads、build 逐页套版式 =====
def demo_02_json_template():
    try:
        import json
        import os
        import tempfile
        from pptx import Presentation

        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, 'template.pptx')
            # 只含母版与版式的空模板
            Presentation().save(template)

            RAW = '''[
  {"layout": 1, "title": "第一页", "bullets": ["营收 +12%", "新增 3 个客户"]},
  {"layout": 1, "title": "第二页", "bullets": ["成本下降", "复购率持平"]}
]'''

            def build(spec, tpl=template):
                prs = Presentation(tpl)
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
            deck.save(os.path.join(td, 'report.pptx'))
            print('从 JSON 生成页数', len(deck.slides))
    except ImportError:
        print('跳过：需要 pip install python-pptx')


demo_02_json_template()


# ===== 03 · 源文节 dotenv 把密钥与路径挪出代码 · 演示 临时 .env、override=True、必填项与带默认值的 getenv =====
def demo_03_dotenv():
    try:
        import os
        import tempfile
        from dotenv import load_dotenv

        with tempfile.TemporaryDirectory() as folder:
            env_path = os.path.join(folder, '.env')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write('SMTP_TOKEN=abc123\nOUTPUT_DIR=./out\nDEBUG=0\n')

            load_dotenv(env_path, override=True)
            token = os.environ['SMTP_TOKEN']
            debug = os.getenv('DEBUG', '0') == '1'
            print('token 长度', len(token), 'debug', debug,
                  '输出目录', os.getenv('OUTPUT_DIR', './default'))
    except ImportError:
        print('跳过：需要 pip install python-dotenv')


demo_03_dotenv()


# ===== 04 · 源文节 Tkinter 最小界面与后台线程 · 演示 queue.Queue + after 轮询、工作线程不碰控件 =====
def demo_04_tkinter():
    try:
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

        # 按约束不创建 tk.Tk() 窗口、不进入 mainloop()（避免 GUI 与无限循环）；
        # root / label 由真实 GUI 层提供，这里只保留线程与轮询骨架并补最小计算调用
        print('tkinter 可用：线程 + 队列 + after 骨架已定义（不创建窗口）')
        print('heavy(21) =', heavy(21))
    except ImportError:
        print('跳过：需要 tkinter 图形环境')


demo_04_tkinter()


# ===== 05 · 源文节 Pillow 图片处理与二维码合成 · 演示 画布/画框/贴图、qrcode 出 PNG、thumbnail 保持比例 =====
def demo_05_pillow_qrcode():
    try:
        import os
        import tempfile
        from PIL import Image, ImageDraw
        import qrcode

        with tempfile.TemporaryDirectory() as td:
            card = Image.new('RGB', (320, 200), 'white')
            draw = ImageDraw.Draw(card)
            draw.rectangle([10, 10, 310, 190], outline='gray', width=2)
            draw.text((20, 20), 'Report 2026', fill='black')

            qr_path = os.path.join(td, 'qr_tmp.png')
            qrcode.make('https://example.com/report').save(qr_path)
            qr = Image.open(qr_path).convert('RGB').resize((120, 120))
            card.paste(qr, (180, 60))
            card.save(os.path.join(td, 'card.png'))

            thumb = card.copy()
            thumb.thumbnail((160, 100))
            thumb.save(os.path.join(td, 'card_thumb.png'))
            print('原图', card.size, '缩略图', thumb.size)
    except ImportError:
        print('跳过：需要 pip install Pillow qrcode')


demo_05_pillow_qrcode()


# ===== 06 · 源文节 moviepy 分段、拼接与加音轨 · 演示 ColorClip 截取、concatenate、AudioArrayClip 内存构建 =====
def demo_06_moviepy():
    try:
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

        def export():
            # 按约束不实际编码：write_videofile 需要 ffmpeg，首次可能联网取回，且会写媒体文件
            final.write_videofile('out.mp4', codec='libx264', audio_codec='aac', fps=24)
            print('已写出 out.mp4，时长', final.duration)

        print('moviepy 可用：分段与音轨已在内存构建；时长', final.duration)
        print('按约束不调用 export()（不编码视频、不访问外网、不写媒体文件）')
    except (ImportError, AttributeError):
        print('跳过：需要 pip install moviepy numpy')


demo_06_moviepy()


# ===== 07 · 源文节 批处理任务的事务性与错误隔离 · 演示 逐条 try/except、先写临时区再 os.replace 原子挪、失败清单 =====
def demo_07_batch_atomic():
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

    with tempfile.TemporaryDirectory() as work:
        src = os.path.join(work, 'src')
        os.makedirs(src)
        dst = os.path.join(work, 'out')
        names = ['a.txt', 'b.txt', 'c.txt']
        for n in names:
            open(os.path.join(src, n), 'w', encoding='utf-8').close()
        files = [os.path.join(src, n) for n in names]
        ok, failed = run_batch(files, dst)
        print('成功', ok, '失败', failed)
        print('产物', sorted(os.listdir(dst)))


demo_07_batch_atomic()


# ===== 08 · 源文节 文件命名 NFC 规范化与跨平台路径 · 演示 NFC 统一名字、pathlib 拼接、parts/name/suffix =====
def demo_08_nfc_path():
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


demo_08_nfc_path()


# ===== 09 · 源文节 练习 1 · 从 .env 读模板路径生成一页 · 演示 load_dotenv + getenv 默认值 + 只含标题的版式 =====
def demo_09_exercise1():
    try:
        import os
        import tempfile
        from dotenv import load_dotenv
        from pptx import Presentation

        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, 'template.pptx')
            Presentation().save(template)
            env_path = os.path.join(td, '.env')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write('TEMPLATE={}\nREPORT_TITLE=季度报告\n'.format(template))

            load_dotenv(env_path, override=True)
            path = os.getenv('TEMPLATE', template)
            prs = Presentation(path)
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            slide.shapes.title.text = os.getenv('REPORT_TITLE', '未命名')
            prs.save(os.path.join(td, 'one.pptx'))
            print('已生成', len(prs.slides), '页')
    except ImportError:
        print('跳过：需要 pip install python-dotenv python-pptx')


demo_09_exercise1()


# ===== 10 · 源文节 练习 2 · 批量写文件时隔离单条失败 · 演示 逐条 try/except、分别返回成功清单与失败清单 =====
def demo_10_exercise2():
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

    with tempfile.TemporaryDirectory() as td:
        print(batch(['a.txt', 'bad.txt', 'c.txt'], td))


demo_10_exercise2()
