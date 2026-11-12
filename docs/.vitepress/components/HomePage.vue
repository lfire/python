<script setup lang="ts">
import { withBase } from 'vitepress'
import PathMap from './PathMap.vue'
import ScenarioMatrix from './ScenarioMatrix.vue'
import ProgressTracker from './ProgressTracker.vue'
import ConceptDiagram from './ConceptDiagram.vue'
import FlowTimeline from './FlowTimeline.vue'
import Callout from './Callout.vue'
import Quiz from './Quiz.vue'

// 站点骨架首页：这里只描述框架本身具备的能力，不含任何课程内容。
const features = [
  { ico: '🧩', t: '随堂问答组件', d: '选择题、结果预测、代码填空都带即时反馈与解析，写正文时一行标签就能插入。' },
  { ico: '🔬', t: '可放大的概念图', d: '点击放大、滚轮与双指缩放、拖拽平移、ESC 关闭 —— 抽象机制可以「看」着讲。' },
  { ico: '▶️', t: '代码块工具条', d: '每个代码块自动带语言标签、复制按钮与结构折叠；长代码可整块收起，Python 代码块另配在线运行入口。' },
  { ico: '🧭', t: '路线与场景矩阵', d: '阶段路线卡片、可按分类筛选的工程场景表已就位，等课程定稿后填入数据即可。' },
  { ico: '📈', t: '本地学习进度', d: '逐页打卡、按阶段汇总、一键清空；数据只存在浏览器里，不会上传。' },
  { ico: '🌗', t: '双主题与全文搜索', d: '浅色 / 深色两套配色，本地全文搜索、目录大纲、上一节 / 下一节都已配好。' },
]
const stats = [
  { n: '27', t: '个交互组件' }, { n: '24', t: '个全局注册' },
  { n: '0', t: '篇正文（待编写）' }, { n: '1', t: '条 Pages 流水线' },
]
// 占位闭环：只用于演示 FlowTimeline 的横向流程交互，不代表已定稿的教学设计。
const loop = [
  { title: '建立直觉', desc: '类比 + 概念图，先知道它解决什么', tone: 'blue' },
  { title: '可运行示例', desc: '每段代码都能跑，带输出', tone: 'green' },
  { title: '逐行拆解', desc: '点开每一行看解释', tone: 'orange' },
  { title: '猜输出 / 填空', desc: '主动回忆比多看一遍有效', tone: 'purple' },
  { title: '动手练习', desc: '带提示与参考解的编程题', tone: 'red' },
  { title: '速记卡', desc: '要点与易错点分开收束', tone: 'gray' },
]
</script>

<template>
  <div class="home">
    <section class="hp-hero">
      <span class="hp-kicker">从零开始 · 交互式中文教程</span>
      <h1>把 <em>Python</em> 学成<br />你真正会用的语言</h1>
      <p>站点框架、设计系统与交互组件已经就绪，教程正文正在编写中。这里会是一套从第一行代码走到工程实战、边读边练的 Python 中文教程。</p>
      <div class="hp-actions">
        <a class="hp-btn main" :href="withBase('/guide/')">🚀 查看学习路线</a>
        <a class="hp-btn alt" :href="withBase('/about/deploy')">🛠️ 本地运行与部署</a>
        <a class="hp-btn alt" href="https://github.com/lfire/python" target="_blank" rel="noopener noreferrer">📦 GitHub 仓库</a>
      </div>
      <div class="hp-stats">
        <div class="hp-stat" v-for="(s, i) in stats" :key="i"><b>{{ s.n }}</b><span>{{ s.t }}</span></div>
      </div>
    </section>

    <section class="hp-section">
      <div class="hp-section-head">
        <div class="eyebrow">Site capabilities</div>
        <h2>先有骨架，再填内容</h2>
        <p>下面这些能力都已经可用且与课程正文解耦：组件靠属性接收数据，写正文时只需要在 Markdown 里插入标签。这一页出现的图示、路线与场景都是中性占位数据。</p>
      </div>
      <FlowTimeline :steps="loop" title="一讲的学习闭环（占位）" direction="horizontal" />
      <div class="hp-grid" style="margin-top:1.6rem">
        <div class="hp-feature" v-for="(f, i) in features" :key="i">
          <div class="ico">{{ f.ico }}</div><h4>{{ f.t }}</h4><p>{{ f.d }}</p>
        </div>
      </div>
    </section>

    <section class="hp-section" id="components">
      <div class="hp-section-head">
        <div class="eyebrow">Component check</div>
        <h2>交互组件自检</h2>
        <p>下面这个示例只用来确认全局组件注册与即时反馈已生效：随堂问答提交后会调用答案回顾组件给出逐项解析。它是组件用法演示，不是课程内容。</p>
      </div>
      <Callout type="tip" title="组件已全局注册" text="在任意 Markdown 里直接写 Quiz、Callout、ConceptDiagram 等标签即可，无需单独 import。" />
      <div style="margin-top:1rem">
        <Quiz no="D-1" q="下面哪个是本站已经注册好的交互组件？" :options='["Quiz 随堂问答", "数据库服务", "应用服务器"]' answer="0" explain="交互组件统一在 .vitepress/theme/index.ts 中全局注册；提交后的逐项解析来自 main 分支新增的 AnswerReview 组件。" />
      </div>
    </section>

    <section class="hp-section" id="roadmap">
      <div class="hp-section-head">
        <div class="eyebrow">Learning path</div>
        <h2>阶段路线（占位）</h2>
        <p>路线卡片、概念图与侧栏共用同一份目录数据。阶段划分定稿后，替换组件里的占位数组并在配置里补齐导航即可。</p>
      </div>
      <PathMap />
      <div style="margin-top:1.2rem">
        <ConceptDiagram type="placeholder" title="占位示意图：可放大、缩放与拖拽" />
      </div>
      <Callout type="tip" title="目录怎么维护？" text="课程页面清单写在 `docs/.vitepress/utils.ts` 的 `LESSONS`，导航与侧栏写在 `config.mts`；两处补齐后，进度汇总与阶段卡片会自动更新。" />
    </section>

    <section class="hp-section" id="scenarios">
      <div class="hp-section-head">
        <div class="eyebrow">Engineering scenarios</div>
        <h2>工程场景矩阵（占位）</h2>
        <p>分类筛选、难度星级、表格列宽与横向滚动都已可用。场景定稿后替换数据行即可。</p>
      </div>
      <ScenarioMatrix />
    </section>

    <section class="hp-section">
      <div class="hp-section-head">
        <div class="eyebrow">Your progress</div>
        <h2>学到哪了，一眼看得见</h2>
        <p>每讲顶部可以「标记学完」，这里会按阶段汇总。进度只保存在你自己的浏览器里，不会上传，也可以一键清空。目录尚未配置时这里会显示提示，属正常状态。</p>
      </div>
      <ProgressTracker />
    </section>

    <section class="hp-cta">
      <h2>想把站点先跑起来？</h2>
      <p style="color:var(--go-muted);font-size:14px;line-height:1.8;margin-bottom:1.3rem">安装依赖后执行 npm run dev 即可本地预览；推送到 main 会由 GitHub Actions 自动发布到 Pages。</p>
      <a class="hp-btn main" style="background:var(--go-brand)" :href="withBase('/about/deploy')">查看运行与部署说明 →</a>
    </section>

    <div style="text-align:center;color:var(--go-muted);font-size:12px;line-height:1.8;margin:2rem 0 .5rem">
      站点框架与交互组件已就绪 · 教程正文待编写<br />
      <a :href="withBase('/about/')" style="text-decoration:none">关于本站 →</a>
    </div>
  </div>
</template>
