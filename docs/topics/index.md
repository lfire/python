---
title: 专题补遗 · 参考课程查漏补缺
description: 回看最初 7 门慕课参考课程后补齐的工程场景缺口：正则、Scrapy 与反爬、自动化测试、办公进阶、深度学习项目、RAG 框架、Flask 实操、数据实战与工程底座。
---

# 专题补遗

主线的 132 讲按「从零到资深」递进，重点放在语言本身与核心机制。回看最初参考的 7 门慕课课程时，我们发现有一批**工程场景**当初只写进了场景清单、正文没有真正展开——例如 Scrapy 多站点采集、接口自动化测试、PPT 自动生成、医学影像项目、RAG 财报问答。

这一板块就是用来补齐它们的：每篇都是独立专题，不占讲次编号，也不改动主线结构；内容按各自主题组织，配可运行代码、对照表、边界提示与练习。想看「参考了什么、覆盖了什么、还缺什么」，请读[参考课程对照与学习路线](/topics/reference-map)。

<Callout type="tip" title="怎么读这一板块" text="按手头任务跳读即可。专题不要求按顺序，也不属于打卡主线；如果只想补齐某个短板，从下面表格直接进去。" />

## 补了哪些缺口

- **正则表达式 re：从字符类到回溯**：全站只有零散的 import re，没有系统讲正则；参考课把它列为工程基础。
- **Scrapy 与反爬合规：从 Spider 到生产采集**：50 场景里列了「Scrapy 多站点采集」「反爬对抗与合规策略」，正文只讲了 asyncio/aiohttp 手写爬虫。
- **接口与 Web UI 自动化测试**：现有 075/076 讲偏单元测试与 Mock，缺接口自动化、Web UI 自动化与测试工程体系。
- **办公自动化进阶：PPT、GUI 与批处理**：124 讲覆盖邮件/PDF/Excel/Word，缺 PPT 生成、GUI、图片视频批处理与完整 Agent 项目。
- **深度学习项目：CNN、RNN、迁移学习与部署**：103 讲已用手写 autograd 与 toy 数据跑通训练循环，但没有真实数据集、CNN/RNN 网络结构、预训练权重与模型导出上线。
- **RAG 框架与大模型 API 实战**：104 讲用标准库模拟核心机制，缺真实框架、向量库、PDF 解析与 API 成本工程。
- **Flask 实操：路由、模板与会话**：083 讲只做框架选型，没有任一框架的分步开发；服务端阶段偏协议与架构。
- **数据分析实战：Jupyter 到报告导出**：50 场景列了疫情/房价分析、医院科室费用透视、CSV/SQL 查询工具，正文未落地。
- **工程底座：Linux、Git、SQL 与多版本**：072 讲讲依赖管理，但缺操作系统、版本管理、协作工具与 SQL 基础这几块工程底座。

## 专题索引

| 专题 | 关联阶段 | 覆盖内容 |
| --- | --- | --- |
| [正则表达式 re：从字符类到回溯](/topics/regex) | L1 | 字符类、量词与贪婪、分组与命名捕获、零宽断言、re 模块 API、回溯与灾难性匹配、常见模式库。 |
| [Scrapy 与反爬合规：从 Spider 到生产采集](/topics/scrapy-antibot) | L6 | Scrapy 架构、Spider / 中间件 / Pipeline、Scrapyd 部署、robots 与限速、登录态与 Ajax 接口、验证码/代理池/字体加密的边界与合规。 |
| [接口与 Web UI 自动化测试](/topics/testing-automation) | L7 | Postman 接口调试、requests 用例层、pytest 参数化与数据驱动、Allure 报告、Selenium Page Object、失败截图与重试、CI 里的测试门禁。 |
| [办公自动化进阶：PPT、GUI 与批处理](/topics/office-advanced) | L2 | python-pptx 生成演示文稿、dotenv 与模板映射、Tkinter 最小 GUI 与多线程、Pillow 图片/二维码、moviepy 视频分段拼接、批量任务与错误隔离。 |
| [深度学习项目：CNN、RNN、迁移学习与部署](/topics/dl-projects) | L9 | 张量与 DataLoader、CNN 卷积动机、RNN/LSTM 序列建模、预训练 ResNet 与迁移学习、GAN 风格生成、MNIST 分类、医学影像端到端流程、模型导出与上线。 |
| [RAG 框架与大模型 API 实战](/topics/rag-frameworks) | L9 | PDF 解析与分块、Embedding 与向量库、LlamaIndex/语义检索、DeepSeek 等 API 调用与流式响应、Token 成本核算、溯源与拒答、Agent 工具调用与预算。 |
| [Flask 实操：路由、模板与会话](/topics/web-frameworks) | L8 | 应用工厂与蓝图、jinja2 模板、请求与响应、Cookie/Session、表单与验证码、SQLAlchemy 集成、错误处理、生产部署与 HTTPS。 |
| [数据分析实战：Jupyter 到报告导出](/topics/data-projects) | L9 | Jupyter 工作流、Pandas 多表联合与透视、Scipy 假设检验、Matplotlib/Seaborn 图表选型、疫情/房价分析、医院科室费用口径校验、报告导出与复现。 |
| [工程底座：Linux、Git、SQL 与多版本](/topics/toolchain-foundation) | L7 | Linux 文件权限与常用命令、Shell 管道、Git 分支与协作、.gitignore 防泄漏、MySQL 表设计与多表查询、pyenv/Anaconda 多版本、venv 与国内镜像。 |
| [参考课程对照与学习路线](/topics/reference-map) | L0 | 7 门慕课参考课的知识地图、与本站 132 讲的逐项映射、专题补遗的落点，以及按目标选路线的建议。 |

<ProgressTracker />

## 回到主线

- [课程总目录（132 讲）](/guide/curriculum)
- [可运行示例代码](/examples/)
- [练习与速查](/practice/)
- [Python 生态与选型地图](/practice/ecosystem)
