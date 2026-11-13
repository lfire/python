<script setup lang="ts">
import { withBase } from 'vitepress'
import PathMap from './PathMap.vue'
import ScenarioMatrix from './ScenarioMatrix.vue'
import ProgressTracker from './ProgressTracker.vue'
import ConceptDiagram from './ConceptDiagram.vue'
import FlowTimeline from './FlowTimeline.vue'
import Callout from './Callout.vue'
import Quiz from './Quiz.vue'

// 由 tools/course/gen_course.py 生成：站点能力与课程规模数据。
const features = [
  { ico: '🔍', t: '逐行讲解', d: '示例代码可以一行行点开看，每一行在做什么、为什么这么写，都写在旁边，不靠猜。' },
  { ico: '🎯', t: '先猜后看', d: '运行结果默认藏起来，先在脑子里跑一遍再揭晓；答错会解释错在哪，而不是只判对错。' },
  { ico: '🧩', t: '随堂检测', d: '选择题、代码填空、结果预测、动手练习交替出现，每讲至少三次主动回忆。' },
  { ico: '🖼️', t: '图文并重', d: '每讲配有可放大的专属概念图，另有分层蓝图与时序图；点击缩放、拖拽平移，抽象机制可以看着讲。' },
  { ico: '🔬', t: '交互实验台', d: '状态逐语句演示、流程时间线、代码结构折叠与表格增强，把「以为懂了」变成能验证的步骤。' },
  { ico: '📈', t: '进度与速记', d: '每讲可打卡，按 13 个阶段汇总；每讲结尾一页纸速记把要点和坑分开列清楚。' },
]
const stats = [
  { n: '13', t: '个递进阶段' }, { n: '132', t: '讲完整课程' },
  { n: '50', t: '个工程场景' }, { n: '27', t: '个交互组件' },
]
const loop = [{"title": "建立直觉", "desc": "类比 + 概念图，先知道它解决什么", "tone": "blue"}, {"title": "可运行示例", "desc": "每段代码都能跑，带真实输出", "tone": "green"}, {"title": "逐行拆解", "desc": "点开每一行看解释", "tone": "orange"}, {"title": "猜输出 / 填空", "desc": "主动回忆比多看一遍有效", "tone": "purple"}, {"title": "动手练习", "desc": "带提示与参考解的编程题", "tone": "red"}, {"title": "速记卡", "desc": "要点与易错点分开收束", "tone": "gray"}]
</script>

<template>
  <div class="home">
    <section class="hp-hero">
      <span class="hp-kicker">从零基础到资深 · 交互式中文教程</span>
      <h1>把 <em>Python</em> 学成<br />你真正会用的语言</h1>
      <p>先别急着写代码。这里把 Python 从第一行 print 铺到解释器源码、高并发架构与生产级工程，做成一条缓坡：13 个阶段、132 讲，不假设你有编程基础，每一讲都会先说清它为什么出现在这里，再慢慢切入主题。</p>
      <div class="hp-actions">
        <a class="hp-btn main" :href="withBase('/guide/before-you-start')">🧭 先读「开始之前」</a>
        <a class="hp-btn alt" :href="withBase('/guide/opening')">🚀 直接从第 001 讲开始</a>
        <a class="hp-btn alt" :href="withBase('/guide/curriculum')">📖 完整课程目录</a>
      </div>
      <div class="hp-stats">
        <div class="hp-stat" v-for="(s, i) in stats" :key="i"><b>{{ s.n }}</b><span>{{ s.t }}</span></div>
      </div>
    </section>

    <section class="hp-section" id="before-you-start">
      <div class="hp-section-head">
        <div class="eyebrow">Before you start</div>
        <h2>先花五分钟，把地图摊开</h2>
        <p>刚开始学一门语言，最容易消耗耐心的往往不是语法，而是不知道自己站在哪里、接下来往哪走。这一节把教程的定位、适合的人群、可选路线和站点的用法先说清楚；读完再开始，会顺很多。</p>
      </div>
      <div class="hp-grid">
        <div class="hp-feature"><div class="ico">🧭</div><h4>三条学习路线</h4><p>零基础顺序学、按短板切入、只查一个具体问题，都能找到自己的入口；不要求从头到尾一字不落。</p></div>
        <div class="hp-feature"><div class="ico">🪜</div><h4>逐级递进</h4><p>先能对，再能快；先单进程，再并发；先会写，再会发布。每讲开头都有一段引入，交代承接、前置与展开顺序。</p></div>
        <div class="hp-feature"><div class="ico">🧰</div><h4>需要准备什么</h4><p>一台能联网的电脑、Python 3.10 以上、一个顺手的编辑器。虚拟环境与工具链会在导学阶段带着装。</p></div>
        <div class="hp-feature"><div class="ico">🎛️</div><h4>站点怎么用</h4><p>逐行讲解、先猜输出、随堂检测、可放大概念图、练习与打卡怎么用，都在开篇页里逐项说明。</p></div>
      </div>
      <div style="margin-top:1.2rem">
        <Callout type="tip" title="不确定从哪开始？" text="就读「开始之前」。它不教你语法，只回答「这套教程是什么、写给谁、我该怎么用」——把这几件事弄清楚，后面每一讲都会好切入得多。" />
      </div>
      <div style="margin-top:1.2rem"><a class="hp-btn main" style="background:var(--go-brand)" :href="withBase('/guide/before-you-start')">读「开始之前」 →</a></div>
    </section>

    <section class="hp-section">
      <div class="hp-section-head">
        <div class="eyebrow">How you learn</div>
        <h2>不是把文档搬上来，而是重新设计学习过程</h2>
        <p>同样的知识点，读一遍和「先猜、再验证、再练一遍」的留存率完全不同。整套课程把交互做成固定节奏：每一讲都按下面的闭环推进，难点另配可放大的图示和逐语句实验台。</p>
      </div>
      <FlowTimeline :steps="loop" title="一讲的学习闭环" direction="horizontal" />
      <div class="hp-grid" style="margin-top:1.6rem">
        <div class="hp-feature" v-for="(f, i) in features" :key="i">
          <div class="ico">{{ f.ico }}</div><h4>{{ f.t }}</h4><p>{{ f.d }}</p>
        </div>
      </div>
    </section>

    <section class="hp-section" id="components">
      <div class="hp-section-head">
        <div class="eyebrow">Component check</div>
        <h2>先试试交互：组件自检</h2>
        <p>下面这个示例用来确认全局组件注册、即时反馈与答案回顾都已生效；它同时也是全站交互形态的一个缩影。</p>
      </div>
      <Callout type="tip" title="组件已全局注册" text="在任意 Markdown 里直接写 Quiz、Callout、ConceptDiagram 等标签即可，无需单独 import。" />
      <div style="margin-top:1rem">
        <Quiz no="D-1" q="关于 Python 的默认值，下面哪种写法是安全的？" :options='["def f(x, buf=[])", "def f(x, buf=None) 并在函数内初始化", "把默认值写成全局列表", "默认值无需考虑可变性"]' answer="1" explain="默认值在定义时只求值一次，可变默认值会被所有调用共享；用 None 作哨兵并在函数体内初始化才是安全写法。" />
      </div>
    </section>

    <section class="hp-section" id="roadmap">
      <div class="hp-section-head">
        <div class="eyebrow">Learning path</div>
        <h2>十三个阶段，一条不跳步的路线</h2>
        <p>顺序按认知负担设计：先建直觉 → 再学语法 → 再拆底层 → 再做工程 → 最后做架构与源码。前一阶段的输出，正好是下一阶段的前置。</p>
      </div>
      <PathMap />
      <div style="margin-top:1.2rem">
        <ConceptDiagram type="flow4" title="一次学习的完整链路" labels="建立直觉|跑通示例|验证边界|工程落地" caption="每一讲都按这条链路组织" />
      </div>
      <Callout type="tip" title="已经有经验？" text="可以先做练习与速查里的能力自评，按短板切入对应阶段；每讲顶部都标了难度与前置，侧栏按阶段分组，随时能跳回来补。" />
    </section>

    <section class="hp-section" id="scenarios">
      <div class="hp-section-head">
        <div class="eyebrow">Engineering scenarios</div>
        <h2>12 类工程场景：分类 × 难度</h2>
        <p>命令行、办公自动化、网络服务、爬虫、数据分析、存储、微服务、云原生、测试质量、AI 工程、安全治理与跨语言底层，每类内部从 ★ 走到 ★★★★★。点分类标签可以筛选。</p>
      </div>
      <ScenarioMatrix />
    </section>

    <section class="hp-section">
      <div class="hp-section-head">
        <div class="eyebrow">Your progress</div>
        <h2>学到哪了，一眼看得见</h2>
        <p>每讲顶部可以「标记学完」，这里会按 13 个阶段汇总。进度只保存在你自己的浏览器里，不会上传，也可以一键清空。</p>
      </div>
      <ProgressTracker />
    </section>

    <section class="hp-cta">
      <h2>准备好写第一行 Python 了吗？</h2>
      <p style="color:var(--go-muted);font-size:14px;line-height:1.8;margin-bottom:1.3rem">先花十分钟认识这门语言与它的取舍，第 002 讲就会带你把环境一次装好。</p>
      <a class="hp-btn main" style="background:var(--go-brand)" :href="withBase('/guide/setup')">从装环境开始 →</a>
    </section>

    <div style="text-align:center;color:var(--go-muted);font-size:12px;line-height:1.8;margin:2rem 0 .5rem">
      为一遍学明白而设计 · 例子均可运行，图示可放大，进度只在本地<br />
      <a :href="withBase('/about/')" style="text-decoration:none">关于本站与内容编排思路 →</a>
    </div>
  </div>
</template>
