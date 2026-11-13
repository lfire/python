<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'

interface Row { cat: string; name: string; desc: string; level: number; prereq: string; link: string }

/** 由 tools/course/gen_course.py 生成：12 大类、50 个工程场景。 */
const rows: Row[] = [
  { cat: '命令行与工具链', name: '待办清单 CLI', desc: 'argparse / click、JSON 原子持久化、退出码与端到端测试', level: 1, prereq: 'L2 容器', link: '/projects/cli-todo' },
  { cat: '命令行与工具链', name: '批量重命名与文件整理器', desc: 'pathlib、dry-run、审计日志与撤销路径', level: 2, prereq: 'L7 工程化', link: '/projects/office-files' },
  { cat: '命令行与工具链', name: '代码生成器与模板引擎', desc: 'AST、Jinja2、入口点与插件注册', level: 3, prereq: 'L5 核心机制', link: '/functions/capstone' },
  { cat: '办公自动化', name: '文件检索与容量统计', desc: 'os.walk、logging、datetime、分类占比报表', level: 1, prereq: 'L1 地基', link: '/projects/office-files' },
  { cat: '办公自动化', name: '邮件 / PDF 批处理', desc: 'yagmail、pypdf 拆分合并、HTML 模板', level: 2, prereq: 'L2 容器', link: '/projects/office-docs' },
  { cat: '办公自动化', name: 'Excel / Word 报表流水线', desc: 'openpyxl、pandas、python-docx 模板渲染', level: 3, prereq: 'L9 数据', link: '/projects/office-docs' },
  { cat: '办公自动化', name: '图片与视频批处理', desc: 'Pillow、二维码、moviepy 分段与拼接', level: 3, prereq: 'L2 容器', link: '/projects/office-docs' },
  { cat: '办公自动化', name: 'Selenium 定时填表', desc: 'WebDriverWait、APScheduler、异常截图', level: 3, prereq: 'L6 并发', link: '/projects/browser-auto' },
  { cat: '网络服务', name: '生产级短链服务', desc: 'Base62、缓存、限流、301/302 与压测', level: 3, prereq: 'L8 服务端', link: '/server/capstone' },
  { cat: '网络服务', name: '图片服务与对象存储', desc: '上传校验、缩略图、ETag、预签名直传', level: 3, prereq: 'L8 服务端', link: '/server/storage' },
  { cat: '网络服务', name: '实时推送与 WebSocket', desc: 'ASGI、心跳、断线重连、跨实例广播', level: 4, prereq: 'L8 服务端', link: '/server/websocket' },
  { cat: '网络服务', name: 'RESTful 开放平台 API', desc: 'OpenAPI、幂等键、版本策略与契约测试', level: 4, prereq: 'L8 服务端', link: '/server/rest-api' },
  { cat: '数据采集与爬虫', name: '静态页面图片批量下载', desc: 'requests、会话复用、重试与本地落盘', level: 1, prereq: 'L1 地基', link: '/concurrency/capstone' },
  { cat: '数据采集与爬虫', name: 'Scrapy 多站点采集', desc: 'Spider、中间件、Pipeline、Scrapyd 部署', level: 3, prereq: 'L6 并发', link: '/concurrency/capstone' },
  { cat: '数据采集与爬虫', name: '登录态与异步接口采集', desc: 'Cookie 池、Token、Ajax 接口逆向', level: 4, prereq: 'L6 并发', link: '/concurrency/capstone' },
  { cat: '数据采集与爬虫', name: '反爬对抗与合规策略', desc: '字体加密、验证码、代理池、robots 与限速', level: 5, prereq: 'L10 分布式', link: '/distributed/security' },
  { cat: '数据处理与分析', name: '疫情 / 房价数据分析', desc: 'Pandas 清洗分组、可视化、报告导出', level: 2, prereq: 'L9 数据', link: '/data-ai/pandas' },
  { cat: '数据处理与分析', name: '日志 ETL 管道', desc: '生成器、窗口聚合、背压、脏数据隔离', level: 3, prereq: 'L6 并发', link: '/projects/data-etl' },
  { cat: '数据处理与分析', name: 'CSV / SQL 查询工具', desc: '表达式解析、多数据源适配与批量写入', level: 3, prereq: 'L8 服务端', link: '/projects/data-etl' },
  { cat: '数据处理与分析', name: '医院科室费用透视', desc: '多表联合、透视表、统计口径校验', level: 3, prereq: 'L9 数据', link: '/data-ai/pandas' },
  { cat: '存储与中间件', name: 'KV ① 内存版', desc: '命令模型、窄接口、过期与契约测试', level: 2, prereq: 'L4 面向对象', link: '/projects/kv-memory' },
  { cat: '存储与中间件', name: 'KV ② 网络协议帧', desc: '长度前缀、asyncio、客户端 SDK', level: 3, prereq: 'L6 并发', link: '/projects/kv-network' },
  { cat: '存储与中间件', name: 'KV ③ WAL 与恢复', desc: '追加写、fsync、重放、快照压缩', level: 4, prereq: 'L10 分布式', link: '/projects/kv-wal' },
  { cat: '存储与中间件', name: 'KV ④ 分片与副本', desc: '一致性哈希、quorum、故障转移', level: 5, prereq: 'L10 分布式', link: '/projects/kv-distributed' },
  { cat: '存储与中间件', name: 'Redis 缓存与分布式锁', desc: '穿透 / 击穿 / 雪崩、租约与幂等', level: 4, prereq: 'L8 服务端', link: '/server/redis' },
  { cat: '微服务架构', name: '自研 RPC 框架', desc: '协议设计、序列化、超时与错误传播', level: 4, prereq: 'L8 服务端', link: '/server/storage' },
  { cat: '微服务架构', name: '电商订单服务', desc: '领域分层、Saga 补偿、契约测试', level: 5, prereq: 'L10 分布式', link: '/distributed/dist-tx' },
  { cat: '微服务架构', name: 'API 网关与熔断', desc: '鉴权、限流、降级、重试退避', level: 4, prereq: 'L10 分布式', link: '/distributed/idempotency' },
  { cat: '微服务架构', name: '秒杀与高并发库存', desc: '原子扣减、削峰、预热与压测', level: 5, prereq: 'L8 服务端', link: '/server/redis' },
  { cat: '云原生与 SRE', name: 'Docker 多阶段构建', desc: '镜像瘦身、非 root、锁文件与冷启动', level: 3, prereq: 'L10 分布式', link: '/distributed/docker-k8s' },
  { cat: '云原生与 SRE', name: 'Kubernetes 部署与 HPA', desc: '资源限制、探针、优雅退出、自动扩缩', level: 4, prereq: 'L10 分布式', link: '/distributed/docker-k8s' },
  { cat: '云原生与 SRE', name: 'GitOps 灰度发布', desc: 'Helm、金丝雀、指标联动回滚', level: 4, prereq: 'L10 分布式', link: '/distributed/gitops' },
  { cat: '云原生与 SRE', name: '全链路可观测平台', desc: 'Trace / Metrics / Log、SLO 与告警降噪', level: 4, prereq: 'L10 分布式', link: '/distributed/gitops' },
  { cat: '云原生与 SRE', name: '分布式任务调度', desc: 'Airflow / Temporal、补数与幂等', level: 4, prereq: 'L10 分布式', link: '/distributed/scheduling' },
  { cat: '测试与质量', name: '接口自动化测试框架', desc: 'pytest、requests、数据驱动与报告', level: 2, prereq: 'L7 工程化', link: '/engineering/pytest' },
  { cat: '测试与质量', name: 'Web UI 自动化测试', desc: 'Selenium、Page Object、失败截图', level: 3, prereq: 'L7 工程化', link: '/engineering/mock' },
  { cat: '测试与质量', name: '属性测试与基准回归', desc: 'hypothesis、pytest-benchmark、CI 阈值', level: 4, prereq: 'L7 工程化', link: '/engineering/property-testing' },
  { cat: '数据与 AI 工程', name: '经典算法建模与调参', desc: '特征工程、交叉验证、网格搜索', level: 3, prereq: 'L9 数据', link: '/data-ai/model-tuning' },
  { cat: '数据与 AI 工程', name: '图像分类与迁移学习', desc: 'PyTorch、DataLoader、CNN、预训练权重', level: 4, prereq: 'L9 数据', link: '/data-ai/deep-learning' },
  { cat: '数据与 AI 工程', name: '漫画脸风格生成', desc: '数据集、训练循环、推理与可视化', level: 4, prereq: 'L9 数据', link: '/data-ai/deep-learning' },
  { cat: '数据与 AI 工程', name: '医学影像端到端判别', desc: '标注数据、CT 可视化、训练与部署', level: 5, prereq: 'L9 数据', link: '/data-ai/deep-learning' },
  { cat: '数据与 AI 工程', name: 'RAG 财报问答系统', desc: 'PDF 解析、向量化、语义检索与溯源', level: 4, prereq: 'L9 数据', link: '/data-ai/llm-engineering' },
  { cat: '数据与 AI 工程', name: '智能选题 / PPT 生成 Agent', desc: 'Prompt 模板、工具调用、python-pptx、成本上限', level: 4, prereq: 'L9 数据', link: '/data-ai/llm-engineering' },
  { cat: '数据与 AI 工程', name: 'AI 网关与流式推理', desc: 'SSE、多供应商适配、限流与 Token 成本', level: 5, prereq: 'L9 数据', link: '/projects/kv-distributed' },
  { cat: '安全与治理', name: '依赖漏洞与 SBOM 审计', desc: '锁文件、哈希校验、镜像扫描', level: 3, prereq: 'L10 分布式', link: '/distributed/security' },
  { cat: '安全与治理', name: '认证授权与审计日志', desc: 'JWT / OAuth2、RBAC、敏感字段脱敏', level: 4, prereq: 'L8 服务端', link: '/server/auth' },
  { cat: '安全与治理', name: '配置与密钥托管', desc: '.env、pydantic-settings、轮换与漂移检测', level: 3, prereq: 'L7 工程化', link: '/engineering/config' },
  { cat: '跨语言与底层', name: 'ctypes / cffi 调用 C 库', desc: 'ABI、内存所有权、GIL 释放', level: 5, prereq: 'L5 核心机制', link: '/advanced/optimization' },
  { cat: '跨语言与底层', name: 'Cython 热点加速', desc: '静态类型、编译、基准与回退', level: 5, prereq: 'L11 资深', link: '/advanced/optimization' },
  { cat: '跨语言与底层', name: 'WASM 与插件沙箱', desc: '宿主边界、导入白名单、资源限制', level: 5, prereq: 'L10 分布式', link: '/distributed/security' },
]
const cats = [
  '全部',
  '命令行与工具链',
  '办公自动化',
  '网络服务',
  '数据采集与爬虫',
  '数据处理与分析',
  '存储与中间件',
  '微服务架构',
  '云原生与 SRE',
  '测试与质量',
  '数据与 AI 工程',
  '安全与治理',
  '跨语言与底层'
]
const active = ref('全部')
const shown = computed(() => active.value === '全部' ? rows : rows.filter(r => r.cat === active.value))
function badge(l: number) { return 'l' + Math.min(5, Math.max(1, l)) }
function stars(l: number) { return '★'.repeat(l) + '☆'.repeat(5 - l) }
</script>

<template>
  <div>
    <div style="display:flex;gap:.35rem;flex-wrap:wrap;margin-bottom:1rem">
      <button v-for="c in cats" :key="c" class="go-btn ghost"
        :style="{fontSize:'12px',padding:'5px 11px',borderColor: active===c ? 'var(--go-brand)':'var(--go-line)', color: active===c ? 'var(--go-brand)':'var(--go-ink)', background: active===c ? 'var(--go-brand-soft)':'transparent'}"
        @click="active = c">{{ c }}</button>
    </div>
    <div style="overflow:hidden;border:1px solid var(--go-line);border-radius:12px;box-shadow:var(--go-shadow)">
      <table class="go-matrix" style="margin:0;width:100%">
        <colgroup>
          <col style="width:14%" /><col style="width:22%" /><col style="width:36%" />
          <col style="width:10%" /><col style="width:18%" />
        </colgroup>
        <thead><tr><th>场景分类</th><th>项目 / 能力</th><th>你会练到什么</th><th>难度</th><th>建议前置</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in shown" :key="i">
            <td><span class="go-badge" :class="badge(r.level)">{{ r.cat }}</span></td>
            <td><a :href="withBase(r.link)" style="font-weight:700;text-decoration:none">{{ r.name }}</a></td>
            <td style="color:var(--go-muted);line-height:1.65">{{ r.desc }}</td>
            <td class="go-stars">{{ stars(r.level) }}</td>
            <td style="color:var(--go-muted);font-size:12px">{{ r.prereq }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="go-sub" style="margin-top:.6rem">
      共 <b>50 个场景</b>覆盖 <b>12 类工程领域</b>，类内按 ★ 到 ★★★★★ 递进；点击分类标签可筛选。
    </div>
  </div>
</template>
