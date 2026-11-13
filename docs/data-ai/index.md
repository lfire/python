---
title: 阶段导览 · 数据与 AI
description: 从数据处理到机器学习、深度学习与大模型应用工程
---

<StageHeader stage='阶段九 · 数据科学与 AI 工程' level='★★★★☆' time='12 讲' goal='从数据处理到机器学习、深度学习与大模型应用工程' prereq='上一阶段' />

# 阶段导览 · 数据与 AI

> 从数据处理到机器学习、深度学习与大模型应用工程。本阶段共 12 讲，覆盖 NumPy / Pandas、可视化与统计、经典算法、集成学习、PyTorch、LLM / RAG / Agent。建议按顺序推进：每讲都先建立直觉、再跑通示例、最后看工程边界，讲与讲之间的依赖关系在下面的地图里一目了然。

## 这个阶段解决什么问题

NumPy / Pandas、可视化与统计、经典算法、集成学习、PyTorch、LLM / RAG / Agent。阶段划分不是按知识点罗列，而是按「学完能交付什么」倒推：前一阶段的输出正好是这一阶段的前置，跳过某一段往往会在后面某讲突然卡住，届时再回来补齐比按顺序学更费时。

<ConceptDiagram type='compare2' title='阶段九 · 数据科学与 AI 工程 · 知识主线' labels='数据|特征|模型|服务' caption='从数据处理到机器学习、深度学习与大模型应用工程' />

<Callout type="tip" title="怎么用这一阶段" text='先读导览确定出口能力，再逐讲打卡；遇到卡点优先回到对应讲的最小示例，而不是直接翻答案。共 12 讲，合计约 500 分钟。' />

## 阶段能力出口

<CheckList id='L9-goals' title='阶段九 · 数据科学与 AI 工程 · 能力自检' :items='["能独立完成本阶段 12 讲中的全部随堂检测", "能说清 NumPy / Pandas、可视化与统计、经典算法、集成学习、PyTorch、LLM / RAG / Agent 各自解决什么问题", "能把本阶段结论接到真实项目并说明代价"]' />

## 讲次地图

| 讲次 | 标题 | 难度 | 建议时长 | 学完能做什么 |
| --- | --- | --- | --- | --- |
| 093 | [NumPy 向量化、广播与内存布局](/data-ai/numpy) | ★★★☆☆ | 40 分钟 | 写出比纯 Python 快一个量级的数值代码 |
| 094 | [Pandas 清洗、分组、透视与时间序列](/data-ai/pandas) | ★★★☆☆ | 45 分钟 | 把脏数据变成可分析的数据集 |
| 095 | [可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization) | ★★☆☆☆ | 35 分钟 | 用图准确表达数据而不是装饰数据 |
| 096 | [统计基础：分布、检验与相关性](/data-ai/statistics) | ★★★☆☆ | 40 分钟 | 在建模前建立对数据的基本判断 |
| 097 | [机器学习流程：特征、划分与评价](/data-ai/ml-workflow) | ★★★☆☆ | 40 分钟 | 建立不会自欺的建模与评估流程 |
| 098 | [经典算法：KNN、线性与逻辑回归](/data-ai/linear-models) | ★★★☆☆ | 40 分钟 | 从最简模型理解偏差方差与优化 |
| 099 | [SVM、核方法、决策树与随机森林](/data-ai/svm-trees) | ★★★☆☆ | 40 分钟 | 掌握非线性模型与其适用边界 |
| 100 | [集成学习：Boosting、XGBoost 与 LightGBM](/data-ai/ensemble) | ★★★★☆ | 40 分钟 | 用组合模型稳定提升表格数据表现 |
| 101 | [无监督学习：KMeans、DBSCAN、PCA 与异常检测](/data-ai/unsupervised) | ★★★☆☆ | 40 分钟 | 在没有标签时从结构里找信息 |
| 102 | [模型调优：交叉验证、正则化与过拟合](/data-ai/model-tuning) | ★★★★☆ | 40 分钟 | 系统性地提升泛化能力 |
| 103 | [深度学习与 PyTorch：张量、自动微分与训练循环](/data-ai/deep-learning) | ★★★★☆ | 50 分钟 | 从零跑通一个神经网络训练 |
| 104 | [LLM 应用工程：Prompt、RAG、Agent 与成本](/data-ai/llm-engineering) | ★★★★☆ | 50 分钟 | 把大模型能力做成可靠、可控、可观测的应用 |

## 学习节奏建议

<StepBox title='数据与 AI · 前五讲推进节奏' :steps='[{"title": "第 1 步：NumPy 向量化、广播与内存布", "body": "写出比纯 Python 快一个量级的数值代码", "tip": "预计 40 分钟，做完随手打卡"}, {"title": "第 2 步：Pandas 清洗、分组、透视与", "body": "把脏数据变成可分析的数据集", "tip": "预计 45 分钟，做完随手打卡"}, {"title": "第 3 步：可视化：Matplotlib /", "body": "用图准确表达数据而不是装饰数据", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 4 步：统计基础：分布、检验与相关性", "body": "在建模前建立对数据的基本判断", "tip": "预计 40 分钟，做完随手打卡"}, {"title": "第 5 步：机器学习流程：特征、划分与评价", "body": "建立不会自欺的建模与评估流程", "tip": "预计 40 分钟，做完随手打卡"}]' />

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先看导览与概念图", "tone": "blue"}, {"title": "逐讲推进", "desc": "跑示例代码并做完随堂检测", "tone": "green"}, {"title": "边界复盘", "desc": "整理易错点与工程代价", "tone": "orange"}, {"title": "进入下一阶段", "desc": "带着出口能力继续", "tone": "purple"}]' direction="horizontal" title='阶段学习闭环' />

## 阶段进度

<ProgressTracker />

[下一阶段：阶段十 · 分布式与云原生](/distributed/)
