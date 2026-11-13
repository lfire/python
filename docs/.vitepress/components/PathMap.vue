<script setup lang="ts">
import { withBase } from 'vitepress'

/** 由 tools/course/gen_course.py 生成：13 个阶段与 config.mts / utils.ts 同源。 */
const stages = [
  { lv: 'L0 · 导学', name: '导学', desc: '语言定位、环境与工具链、第一行代码、执行模型与学习路线', link: '/guide/', color: '#868e96', meta: '5 讲' },
  { lv: 'L1 · 编程地基', name: '编程地基', desc: '对象模型、变量绑定、数值与字符串、运算符、控制流、IO 与异常', link: '/foundation/', color: '#2b8a3e', meta: '11 讲' },
  { lv: 'L2 · 容器与序列', name: '容器与序列', desc: '序列协议、list / tuple / dict / set、推导式', link: '/containers/', color: '#1c7ed6', meta: '11 讲' },
  { lv: 'L3 · 函数与抽象', name: '函数与抽象', desc: '参数形态、作用域闭包、高阶函数、装饰器、模块包与类型系统', link: '/functions/', color: '#7048e8', meta: '10 讲' },
  { lv: 'L4 · 面向对象', name: '面向对象', desc: '类与实例、MRO、描述符、特殊方法、ABC、元类、dataclass', link: '/oop/', color: '#e8590c', meta: '11 讲' },
  { lv: 'L5 · 核心机制', name: '核心机制', desc: '编译流程、字节码、帧与命名空间、引用计数 GC、GIL、导入系统、性', link: '/core/', color: '#495057', meta: '11 讲' },
  { lv: 'L6 · 并发与异步', name: '并发与异步', desc: '线程与同步、进程与 IPC、IO 多路复用、生成器协程、asynci', link: '/concurrency/', color: '#e8590c', meta: '11 讲' },
  { lv: 'L7 · 工程化', name: '工程化', desc: '项目结构、依赖与锁、规范与类型、测试与 Mock、日志配置、打包与 ', link: '/engineering/', color: '#0ca678', meta: '11 讲' },
  { lv: 'L8 · 服务端与数据', name: '服务端与数据', desc: 'HTTP / ASGI、FastAPI / Flask / Djan', link: '/server/', color: '#1c7ed6', meta: '11 讲' },
  { lv: 'L9 · 数据与 AI', name: '数据与 AI', desc: 'NumPy / Pandas、可视化与统计、经典算法、集成学习、Py', link: '/data-ai/', color: '#7048e8', meta: '12 讲' },
  { lv: 'L10 · 分布式云原生', name: '分布式云原生', desc: '一致性、幂等、分布式事务、分片、容器与 K8s、调度、SRE、安全', link: '/distributed/', color: '#c92a2a', meta: '9 讲' },
  { lv: 'L11 · 资深进阶', name: '资深进阶', desc: 'CPython 源码、内存分配器与 GC、导入与事件循环源码、 sp', link: '/advanced/', color: '#495057', meta: '8 讲' },
  { lv: 'L12 · 工程实战', name: '工程实战', desc: 'CLI、办公自动化、Web、爬虫、数据、AI、存储、分布式与贯穿式 ', link: '/projects/', color: '#c92a2a', meta: '11 讲' },
]
</script>

<template>
  <div class="go-path">
    <a v-for="(s, i) in stages" :key="i" class="go-path-card" :href="withBase(s.link)" :style="{borderTop:'3px solid '+s.color}">
      <div class="lv" :style="{color:s.color}">{{ s.lv }} <span style="color:var(--go-muted);font-weight:600">· {{ s.meta }}</span></div>
      <div class="nm">{{ s.name }}</div>
      <div class="ds">{{ s.desc }}</div>
      <div style="margin-top:.7rem;font-size:12px;font-weight:700" :style="{color:s.color}">进入阶段 →</div>
    </a>
  </div>
</template>
