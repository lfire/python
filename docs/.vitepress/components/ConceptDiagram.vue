<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, useId } from 'vue'
import ConceptDiagramSvg from './ConceptDiagramSvg.vue'

interface Node { x: number; y: number; w: number; h: number; label: string; sub?: string; tone?: string }
interface Arrow { x1: number; y1: number; x2: number; y2: number; label?: string }
interface Diagram { h: number; nodes: Node[]; arrows: Arrow[]; caption?: string }

const TONES: Record<string, string> = {
  orange: 'var(--go-brand)', blue: 'var(--go-blue)', green: 'var(--go-green)',
  purple: 'var(--go-purple)', red: 'var(--go-red)', gray: 'var(--go-muted)',
}

/**
 * 概念图数据与布局函数：由 .workbuddy/gen_assets.py 注入。
 */
type N = { label: string; sub?: string; tone?: string }

/** 横向流程：n 个节点等宽排列，自动补箭头。 */
function row(items: N[], caption: string, boxH = 62): Diagram {
  const n = items.length
  const gap = n > 1 ? 30 : 0
  const w = Math.min(158, Math.floor((640 - gap * (n - 1)) / n))
  const y = 48
  const total = n * w + (n - 1) * gap
  const x0 = Math.round((680 - total) / 2)
  const nodes: Node[] = items.map((it, i) => ({ x: x0 + i * (w + gap), y, w, h: boxH, ...it }))
  const arrows: Arrow[] = []
  for (let i = 0; i < n - 1; i++) {
    arrows.push({ x1: nodes[i].x + w, y1: y + boxH / 2, x2: nodes[i + 1].x, y2: y + boxH / 2 })
  }
  return { h: y + boxH + 46, nodes, arrows, caption }
}

/** 纵向分层：每层横排，层与层之间用一条箭头串起来。 */
function layers(rows: N[][], caption: string): Diagram {
  const boxH = 58, rowGap = 42, y0 = 38
  const nodes: Node[] = [], arrows: Arrow[] = []
  rows.forEach((r, ri) => {
    const n = r.length, gap = 24
    const w = Math.min(200, Math.floor((640 - gap * (n - 1)) / n))
    const total = n * w + (n - 1) * gap
    const x0 = Math.round((680 - total) / 2)
    const y = y0 + ri * (boxH + rowGap)
    r.forEach((it, i) => nodes.push({ x: x0 + i * (w + gap), y, w, h: boxH, ...it }))
    if (ri > 0) arrows.push({ x1: 340, y1: y - rowGap + 8, x2: 340, y2: y - 4 })
  })
  return { h: y0 + rows.length * boxH + (rows.length - 1) * rowGap + 40, nodes, arrows, caption }
}

/** 中心辐射：一个中心节点 + 若干外围节点。 */
function hub(center: N, leaves: N[], caption: string): Diagram {
  const cw = 200, ch = 62, cx = 210, cy = 96
  const nodes: Node[] = [{ x: cx, y: cy, w: cw, h: ch, ...center }]
  const arrows: Arrow[] = []
  const lw = 170, lh = 56, lx = 460
  leaves.forEach((it, i) => {
    const ly = 26 + i * 72
    nodes.push({ x: lx, y: ly, w: lw, h: lh, ...it })
    arrows.push({ x1: cx + cw, y1: cy + ch / 2, x2: lx, y2: ly + lh / 2 })
  })
  return { h: Math.max(190, 26 + leaves.length * 72 + 18), nodes, arrows, caption }
}

/** 双栏对照：用于「A 与 B 有什么不同」。 */
function cols(left: N[], right: N[], caption: string): Diagram {
  const nodes: Node[] = []
  const place = (list: N[], x: number) =>
    list.forEach((it, i) => nodes.push({ x, y: 38 + i * 72, w: 262, h: 58, ...it }))
  place(left, 36); place(right, 382)
  const h = Math.max(left.length, right.length) * 72 + 58
  return { h, nodes, arrows: [{ x1: 300, y1: h / 2, x2: 380, y2: h / 2, label: '对比' }], caption }
}

/**
 * 概念图布局模板（与课程内容无关）。
 * 每讲通过 type 选布局、通过 labels/caption 覆盖节点文字，因此 132 讲各有专属图。
 * 布局函数 row / layers / hub / cols 与全部缩放交互都在本文件里，数据只是参数。
 */
const D: Record<string, Diagram> = {
  flow3: row([
    { label: '输入', sub: '起点与前置', tone: 'blue' },
    { label: '处理', sub: '核心规则', tone: 'purple' },
    { label: '输出', sub: '结果与代价', tone: 'green' },
  ], '三段式流程：从输入到输出，中间是规则生效的地方'),
  flow4: row([
    { label: '触发', sub: '谁发起', tone: 'blue' },
    { label: '检查', sub: '前置条件', tone: 'orange' },
    { label: '执行', sub: '状态变化', tone: 'purple' },
    { label: '收尾', sub: '结果与清理', tone: 'green' },
  ], '四段式流程：注意检查与收尾两段最容易被省略'),
  layers3: layers([
    [{ label: '接口层', sub: '对外契约', tone: 'blue' }],
    [{ label: '逻辑层', sub: '规则与状态', tone: 'purple' }, { label: '旁路', sub: '异常与降级', tone: 'orange' }],
    [{ label: '资源层', sub: 'IO 与存储', tone: 'green' }],
  ], '分层视角：每一层只依赖下一层提供的能力'),
  hub4: hub(
    { label: '核心机制', sub: '被多个环节共享', tone: 'purple' },
    [{ label: '可读性', sub: '表达成本', tone: 'blue' },
     { label: '性能', sub: '时间空间', tone: 'orange' },
     { label: '正确性', sub: '边界与失败', tone: 'green' }],
    '一个机制往往同时影响可读性、性能与正确性'),
  compare2: cols(
    [{ label: '方案 A', sub: '直接写法', tone: 'blue' }, { label: '特点', sub: '简单但边界少', tone: 'blue' }],
    [{ label: '方案 B', sub: '工程写法', tone: 'green' }, { label: '特点', sub: '显式且可测', tone: 'green' }],
    '两栏对照：差异通常不在结果，而在失败时的表现'),
  placeholder: row([
    { label: '概念一', sub: '建立直觉', tone: 'blue' },
    { label: '概念二', sub: '验证规则', tone: 'purple' },
    { label: '概念三', sub: '工程落地', tone: 'green' },
  ], '占位示意图：按 type 与 labels 可替换为任意主题'),
}

const props = defineProps<{
  type?: string
  title?: string
  labels?: string
  caption?: string
}>()
const uid = useId().replace(/:/g, '')
const diagram = computed<Diagram>(() => {
  const base = D[props.type || 'placeholder'] || D['placeholder']
  if (!props.labels && !props.caption) return base
  let nodes = base.nodes
  if (props.labels) {
    const parts = String(props.labels || '').split('|').map((s) => s.trim())
    nodes = base.nodes.map((n, i) => {
      const raw = parts[i]
      if (!raw) return n
      const [label, sub] = raw.split('::').map((s) => s.trim())
      return { ...n, label, sub: sub || n.sub }
    })
  }
  return { ...base, nodes, caption: props.caption ?? base.caption }
})
/* 放大查看：滚轮无极缩放（以指针为锚点）+ 拖拽平移画布。
   画布使用固定的 680px 逻辑宽度（与 SVG viewBox 一致），缩放/平移全部由 transform 承担，
   这样窗口尺寸变化不会改变内容本身的坐标系，锚点缩放的计算也始终稳定。 */
const zoomOpen = ref(false)
const scale = ref(1)      // 绝对倍率：1 = 680px 逻辑宽度按 1:1 渲染
const fitScale = ref(1)   // 「适应窗口」倍率，同时作为缩放上下限与百分比的基准
const panX = ref(0)
const panY = ref(0)
const dragging = ref(false)
const viewport = ref<HTMLElement | null>(null)
const BASE_W = 680
const PAD = 28            // 画布四周留白
const MIN_RATIO = 0.4     // 相对适应窗口：最小缩到 40%
const MAX_RATIO = 8       // 相对适应窗口：最大放到 800%
const zoomLevel = computed(() => Math.round(scale.value / (fitScale.value || 1) * 100))
let prevOverflow = ''

const canvasStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`,
  transformOrigin: '0 0',
}))

/** 按视口与图的原始比例算出「整图完整可见」的倍率，并把画布居中。 */
function fitView() {
  const el = viewport.value
  if (!el) return
  const vw = el.clientWidth
  const vh = el.clientHeight
  const h = diagram.value.h || 200
  // 窄屏按宽度适配，固定 28px 留白会占掉太多，缩到视口的 3% 保证弹层里的图不小于正文
  const pad = Math.min(PAD, vw * 0.03)
  const s = Math.max(0.05, Math.min((vw - pad * 2) / BASE_W, (vh - pad * 2) / h))
  fitScale.value = s
  scale.value = s
  panX.value = (vw - BASE_W * s) / 2
  panY.value = (vh - h * s) / 2
}

/** 窗口尺寸变化时保持用户当前的相对倍率，只重算适配基准，不把画面突然打回 100%。 */
function onResize() {
  if (!zoomOpen.value) return
  const el = viewport.value
  if (!el) return
  const ratio = scale.value / (fitScale.value || 1)
  fitView()
  if (Math.abs(ratio - 1) > 0.001) {
    const r = el.getBoundingClientRect()
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, ratio)
  }
}

function openZoom() {
  if (zoomOpen.value) return
  zoomOpen.value = true
  prevOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  // 等 flex 布局稳定后再算垂直居中，避免首帧 clientHeight 还没定下
  nextTick(() => requestAnimationFrame(() => requestAnimationFrame(fitView)))
}
function closeZoom() {
  if (!zoomOpen.value) return
  zoomOpen.value = false
  dragging.value = false
  pointers.clear()
  document.body.style.overflow = prevOverflow
  prevOverflow = ''
}

/** 以 (clientX, clientY) 为锚点缩放：锚点下的内容保持在原位置。 */
function zoomAt(clientX: number, clientY: number, factor: number) {
  const el = viewport.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const mx = clientX - rect.left
  const my = clientY - rect.top
  const cx = (mx - panX.value) / scale.value
  const cy = (my - panY.value) / scale.value
  const min = fitScale.value * MIN_RATIO
  const max = fitScale.value * MAX_RATIO
  const next = Math.min(max, Math.max(min, scale.value * factor))
  if (Math.abs(next - scale.value) < 0.0001) return
  scale.value = next
  panX.value = mx - cx * next
  panY.value = my - cy * next
}

function onWheel(e: WheelEvent) {
  // deltaY 越大缩得越多，用指数换算成连续倍率，触屏板的细小滚动也能平滑响应
  zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * 0.0015))
}
function zoomByStep(factor: number) {
  const el = viewport.value
  if (!el) return
  const r = el.getBoundingClientRect()
  zoomAt(r.left + r.width / 2, r.top + r.height / 2, factor)
}
function onDblClick() { fitView() }

/** 单指拖拽平移；双指捏合缩放（touch-action:none 会禁用浏览器原生缩放，必须自己实现）。 */
interface Pointer { id: number; x: number; y: number }
const pointers = new Map<number, Pointer>()
let dragStart = { x: 0, y: 0, px: 0, py: 0, id: -1 }
let pinchStart = { dist: 1, mx: 0, my: 0 }

function startDrag(p: Pointer) {
  dragStart = { x: p.x, y: p.y, px: panX.value, py: panY.value, id: p.id }
}
function pinchState() {
  const [a, b] = [...pointers.values()]
  return {
    dist: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y)),
    mx: (a.x + b.x) / 2,
    my: (a.y + b.y) / 2,
  }
}
function onPointerDown(e: PointerEvent) {
  if (e.pointerType === 'mouse' && e.button !== 0) return
  try { (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId) } catch { /* 非活跃指针时忽略 */ }
  pointers.set(e.pointerId, { id: e.pointerId, x: e.clientX, y: e.clientY })
  if (pointers.size === 1) {
    dragging.value = true
    startDrag([...pointers.values()][0])
  } else if (pointers.size === 2) {
    dragging.value = false
    pinchStart = pinchState()
  }
}
function onPointerMove(e: PointerEvent) {
  if (!pointers.has(e.pointerId)) return
  pointers.set(e.pointerId, { id: e.pointerId, x: e.clientX, y: e.clientY })
  if (pointers.size >= 2) {
    const now = pinchState()
    zoomAt(now.mx, now.my, now.dist / pinchStart.dist)
    // 捏合的同时两指整体移动，也要跟着平移，观感才跟手
    panX.value += now.mx - pinchStart.mx
    panY.value += now.my - pinchStart.my
    pinchStart = now
    return
  }
  if (!dragging.value || e.pointerId !== dragStart.id) return
  panX.value = dragStart.px + (e.clientX - dragStart.x)
  panY.value = dragStart.py + (e.clientY - dragStart.y)
}
function onPointerUp(e: PointerEvent) {
  pointers.delete(e.pointerId)
  const rest = [...pointers.values()]
  if (rest.length === 1) {
    // 双指变成单指时无缝接着拖，避免画面跳一下
    dragging.value = true
    startDrag(rest[0])
  } else if (rest.length === 0) {
    dragging.value = false
    dragStart.id = -1
  }
}

function onKeydown(e: KeyboardEvent) {
  if (!zoomOpen.value) return
  if (e.key === 'Escape') closeZoom()
  else if (e.key === '+' || e.key === '=') zoomByStep(1.2)
  else if (e.key === '-' || e.key === '_') zoomByStep(1 / 1.2)
  else if (e.key === '0') fitView()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  if (zoomOpen.value) document.body.style.overflow = prevOverflow
})
</script>

<template>
  <figure class="go-figure">
    <div class="go-fig-head">
      <div v-if="title" class="go-eyebrow">{{ title }}</div>
      <span v-else />
      <button class="go-zoom-btn" type="button" :aria-label="`放大查看：${title || '概念图'}`" @click="openZoom">
        ⤢ 放大查看
      </button>
    </div>

    <div class="go-fig-frame" role="button" tabindex="0"
      :aria-label="`点击放大查看：${title || '概念图'}`"
      @click="openZoom" @keydown.enter.prevent="openZoom" @keydown.space.prevent="openZoom">
      <ConceptDiagramSvg :diagram="diagram" :uid="uid" />
    </div>

    <figcaption v-if="diagram.caption" class="go-fig-caption">{{ diagram.caption }}</figcaption>

    <Teleport to="body">
      <div v-if="zoomOpen" class="go-lightbox" role="dialog" aria-modal="true"
        :aria-label="title || '放大查看概念图'" @click.self="closeZoom">
        <div class="go-lightbox-panel">
          <div class="go-lightbox-head">
            <b>{{ title || '概念图' }}</b>
            <div class="go-lightbox-actions">
              <button class="go-btn ghost" type="button" aria-label="缩小" @click="zoomByStep(1 / 1.2)">−</button>
              <span class="go-zoom-level" aria-live="polite">{{ zoomLevel }}%</span>
              <button class="go-btn ghost" type="button" aria-label="放大" @click="zoomByStep(1.2)">＋</button>
              <button class="go-btn ghost" type="button" @click="fitView">适应窗口</button>
              <button class="go-btn ghost" type="button" aria-label="关闭放大" @click="closeZoom">✕ 关闭</button>
            </div>
          </div>
          <div ref="viewport" class="go-lightbox-body" :class="{ dragging }"
            @wheel.prevent="onWheel" @pointerdown="onPointerDown" @pointermove="onPointerMove"
            @pointerup="onPointerUp" @pointercancel="onPointerUp" @dblclick="onDblClick">
            <div class="go-zoom-canvas" :style="canvasStyle">
              <ConceptDiagramSvg :diagram="diagram" :uid="uid + '-zoom'" />
            </div>
          </div>
          <div class="go-lightbox-foot">
            <span v-if="diagram.caption">{{ diagram.caption }} · </span>100% 为适应窗口 · 滚轮 / 双指捏合缩放 · 拖拽平移 · 双击或 0 键复位 · ESC 关闭
          </div>
        </div>
      </div>
    </Teleport>
  </figure>
</template>
