"""data-projects 专题示例：数据分析实战：Jupyter 到报告导出

对应课程页：/topics/data-projects
GitHub 源文件：https://github.com/lfire/python/blob/main/examples/topics/data-projects.py

依赖安装（可选，第三方段缺库时会自动跳过）：
    python3 -m pip install pandas numpy scipy seaborn matplotlib
    # 需要把 Notebook 或 HTML 转成 PDF 时再按需追加
    python3 -m pip install nbconvert weasyprint

运行命令：
    python3 examples/topics/data-projects.py

说明：本文件按源专题 tools/course/topics/data-projects.md 中 python 代码块的出现顺序整理。
纯标准库段（csv / sqlite3 / collections）在纯净环境直接跑出结果；用到
pandas / numpy / scipy / seaborn / matplotlib 的段用 try/except 包成可选段，
缺库时打印跳过提示。绘图用 Agg 后端只写文件不弹窗口，导出与图片都写入
tempfile.TemporaryDirectory() 自动清理，不改动仓库里已有文件。
"""


# ===== 01 · 源文节 装好依赖与固定随机种子 · 演示 打印依赖版本写进报告末尾供复核 =====
def demo_01_versions():
    try:
        import pandas as pd, numpy as np, scipy, matplotlib
        print('pandas', pd.__version__, 'numpy', np.__version__,
              'scipy', scipy.__version__, 'matplotlib', matplotlib.__version__)
    except ImportError:
        print('跳过：需要 pip install pandas numpy scipy matplotlib')


demo_01_versions()


# ===== 02 · 源文节 纯标准库 csv 的等价管道 · 演示 空费用记成 None 并按科室加口径分组算合计例数次均 =====
def demo_02_stdlib_csv():
    import csv, io
    from collections import defaultdict

    RAW = """dept,channel,day,fee
内科,门诊,2024-03-01,320
内科,门诊,2024-03-01,
内科,住院,2024-03-01,8600
外科,门诊,2024-03-01,410
外科,住院,2024-03-01,12000
外科,住院,2024-03-02,9800
"""

    def load(text):
        for row in csv.DictReader(io.StringIO(text)):
            fee = row['fee'].strip()
            yield row['dept'].strip(), row['channel'].strip(), (float(fee) if fee else None)

    rows = list(load(RAW))
    clean = [r for r in rows if r[2] is not None]
    print('原始行', len(rows), '有效行', len(clean))

    total, count = defaultdict(float), defaultdict(int)
    for dept, channel, fee in clean:
        total[(dept, channel)] += fee
        count[(dept, channel)] += 1
    for key in sorted(total):
        print(key, '合计', round(total[key], 2), '例数', count[key],
              '次均', round(total[key] / count[key], 2))


demo_02_stdlib_csv()


# ===== 03 · 源文节 Pandas 版本的读取与清洗 · 演示 read_csv 定类型查缺失重复规整后 groupby 聚合 =====
def demo_03_pandas_read():
    try:
        import pandas as pd
        import io

        RAW = """dept,channel,day,fee
内科,门诊,2024-03-01,320
内科,门诊,2024-03-01,
内科,住院,2024-03-01,8600
外科,门诊,2024-03-01,410
外科,住院,2024-03-01,12000
外科,住院,2024-03-02,9800
"""
        df = pd.read_csv(io.StringIO(RAW), parse_dates=['day'], na_values=[''])
        print('列类型', {k: str(v) for k, v in df.dtypes.items()})
        print('缺失费用', int(df['fee'].isna().sum()), '重复行', int(df.duplicated().sum()))
        df['dept'] = df['dept'].str.strip()
        df = df.drop_duplicates()
        clean = df.dropna(subset=['fee']).copy()
        print(clean.groupby('channel')['fee'].agg(['count', 'sum', 'mean']).round(2))
    except ImportError:
        print('跳过：需要 pip install pandas')


demo_03_pandas_read()


# ===== 04 · 源文节 从 merge 到透视与合计复核 · 演示 many_to_one 合并维表 pivot_table 与行列合计复核 =====
def demo_04_merge_pivot():
    try:
        import pandas as pd

        visits = pd.DataFrame({
            'dept': ['内科', '内科', '外科', '外科'],
            'channel': ['门诊', '住院', '门诊', '住院'],
            'fee': [320.0, 8600.0, 410.0, 12000.0],
        })
        meta = pd.DataFrame({'dept': ['内科', '外科'], 'building': ['A', 'B']})
        merged = pd.merge(visits, meta, on='dept', how='left',
                          validate='many_to_one', indicator=True)
        print('匹配来源', merged['_merge'].value_counts().to_dict())

        pt = merged.pivot_table(index='dept', columns='channel', values='fee',
                                aggfunc='sum', fill_value=0)
        print(pt)
        print('列合计', pt.sum(axis=0).to_dict(), '行合计', pt.sum(axis=1).to_dict())
        print('明细总额', float(visits['fee'].sum()))

        g = merged.groupby(['dept', 'channel'])['fee'].agg(['sum', 'count'])
        g['avg'] = (g['sum'] / g['count']).round(2)
        print(g)
    except ImportError:
        print('跳过：需要 pip install pandas')


demo_04_merge_pivot()


# ===== 05 · 源文节 Scipy 概率分布与假设检验 · 演示 验正态方差齐 Welch t 检验 秩和检验 置信区间 卡方 =====
def demo_05_scipy():
    try:
        import numpy as np
        from scipy import stats

        rng = np.random.default_rng(7)
        a = rng.normal(loc=320, scale=45, size=40)   # 改版前门诊费用
        b = rng.normal(loc=348, scale=50, size=38)   # 改版后门诊费用

        print('shapiro a', round(stats.shapiro(a).pvalue, 4))
        print('levene', round(stats.levene(a, b).pvalue, 4))
        t = stats.ttest_ind(a, b, equal_var=False)
        print('welch t', round(t.statistic, 3), 'p', round(t.pvalue, 4))
        print('mannwhitney p', round(stats.mannwhitneyu(a, b, alternative='two-sided').pvalue, 4))
        ci = stats.t.interval(0.95, len(a) - 1, loc=a.mean(), scale=stats.sem(a))
        print('ci95', tuple(round(v, 2) for v in ci))
        print('chi2 拟合优度', round(stats.chisquare([18, 22, 20, 25]).pvalue, 4))
    except ImportError:
        print('跳过：需要 pip install numpy scipy')


demo_05_scipy()


# ===== 06 · 源文节 Matplotlib 与 Seaborn 的图表选型 · 演示 Agg 后端无窗口绘图 长表语义映射 图片写临时目录 =====
def demo_06_plot():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import tempfile
        from pathlib import Path

        sns.set_theme(style='whitegrid')
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        df = pd.DataFrame({
            'city': ['北京', '上海', '广州', '深圳'] * 3,
            'quarter': ['Q1'] * 4 + ['Q2'] * 4 + ['Q3'] * 4,
            'price': [61, 58, 32, 54, 62, 59, 33, 55, 63, 60, 34, 56],
        })
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        sns.lineplot(data=df, x='quarter', y='price', hue='city', marker='o', ax=axes[0])
        axes[0].set_title('一线城市季度均价走势')
        sns.barplot(data=df, x='city', y='price', ax=axes[1])
        axes[1].set_title('各城市季度均值')
        fig.tight_layout()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'price_report.png'
            fig.savefig(str(out), dpi=150, bbox_inches='tight')
            print('图片写入临时目录将自动清理', out.name)
        print('图片尺寸', fig.get_size_inches())
    except ImportError:
        print('跳过：需要 pip install pandas matplotlib seaborn')


demo_06_plot()


# ===== 07 · 源文节 CSV 与 SQL 查询工具的最小实现 · 演示 csv 灌 sqlite3 内存库 显式转 float 参数化只读查询 =====
def demo_07_csv_sql():
    import csv, io, sqlite3

    RAW = """dept,channel,fee
内科,门诊,320
内科,住院,8600
外科,门诊,410
外科,住院,12000
"""
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE fees (dept TEXT, channel TEXT, fee REAL)')
    con.executemany('INSERT INTO fees VALUES (?, ?, ?)',
                    [(r['dept'], r['channel'], float(r['fee']))
                     for r in csv.DictReader(io.StringIO(RAW))])
    con.commit()
    con.execute('PRAGMA query_only=ON')

    sql = ('SELECT dept, SUM(fee) AS total FROM fees '
           'WHERE channel = ? GROUP BY dept ORDER BY total DESC')
    print('住院合计', con.execute(sql, ('住院',)).fetchall())
    print('全院合计', con.execute('SELECT ROUND(SUM(fee), 2) FROM fees').fetchone()[0])
    con.close()


demo_07_csv_sql()


# ===== 08 · 源文节 报告导出为 HTML 与 PDF 与结果复核 · 演示 to_html 加 utf-8 骨架写临时目录 to_csv 回读核对合计 =====
def demo_08_export():
    try:
        import pandas as pd
        import io
        import tempfile
        from pathlib import Path

        df = pd.DataFrame({
            '科室': ['内科', '外科'],
            '门诊次均': [320.0, 410.0],
            '住院次均': [8600.0, 12000.0],
        })
        page = ('<!doctype html><html><head><meta charset="utf-8">'
                '<title>费用报告</title></head><body><h1>科室费用汇总</h1>')
        page += df.to_html(index=False, border=1)
        page += '<p>口径：门诊与住院分别统计，缺失费用不计入分子与分母。</p></body></html>'
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.html'
            with open(report, 'w', encoding='utf-8') as f:
                f.write(page)
            print('报告写入临时目录将自动清理', report.name)

        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        back = pd.read_csv(buf)
        print('导出前后合计一致',
              round(back['门诊次均'].sum(), 2) == round(df['门诊次均'].sum(), 2))
        print('HTML 字节数', len(page.encode('utf-8')))
    except ImportError:
        print('跳过：需要 pip install pandas')


demo_08_export()


# ===== 09 · 源文节 练习 1 · 演示 空值与门诊行跳过 按科室算住院次均费用 =====
def demo_09_exercise1():
    import csv, io
    from collections import defaultdict

    raw = """dept,channel,fee
内科,住院,8600
内科,住院,9400
外科,住院,12000
内科,住院,
外科,门诊,410
"""
    total, count = defaultdict(float), defaultdict(int)
    for r in csv.DictReader(io.StringIO(raw)):
        fee = r['fee'].strip()
        if r['channel'] != '住院' or not fee:
            continue
        total[r['dept']] += float(fee)
        count[r['dept']] += 1
    result = {d: round(total[d] / count[d], 2) for d in sorted(total)}
    print(result)   # 内科 9000.0，外科 12000.0


demo_09_exercise1()


# ===== 10 · 源文节 练习 2 · 演示 pivot_table 转宽表 用 Welch 检验比较门诊与住院费用 =====
def demo_10_exercise2():
    try:
        import pandas as pd
        from scipy import stats

        df = pd.DataFrame({
            'dept': ['内科'] * 3 + ['外科'] * 3,
            'channel': ['门诊', '门诊', '住院'] * 2,
            'fee': [300, 340, 8600, 400, 420, 12000],
        })
        pt = df.pivot_table(index='dept', columns='channel', values='fee', aggfunc='sum')
        print(pt)
        out = df[df['channel'] == '门诊']['fee']
        inn = df[df['channel'] == '住院']['fee']
        t = stats.ttest_ind(out, inn, equal_var=False)
        print('welch p', round(t.pvalue, 4))
        # 两类费用计费机制不同、量级差一个数量级，合并样本没有共同分布；
        # 方差明显不齐时把 equal_var 设为 False 走 Welch 检验。
    except ImportError:
        print('跳过：需要 pip install pandas scipy')


demo_10_exercise2()
