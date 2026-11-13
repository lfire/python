---
title: 阶段导览 · 容器与序列
description: 把 Python 最常用的内置容器用到知其所以然
---

<StageHeader stage='阶段二 · 容器与序列' level='★☆☆☆☆' time='11 讲' goal='把 Python 最常用的内置容器用到知其所以然' prereq='上一阶段' />

# 阶段导览 · 容器与序列

> 把 Python 最常用的内置容器用到知其所以然。本阶段共 11 讲，覆盖 序列协议、list / tuple / dict / set、推导式、迭代器与生成器。建议按顺序推进：每讲都先建立直觉、再跑通示例、最后看工程边界，讲与讲之间的依赖关系在下面的地图里一目了然。

## 这个阶段解决什么问题

序列协议、list / tuple / dict / set、推导式、迭代器与生成器。阶段划分不是按知识点罗列，而是按「学完能交付什么」倒推：前一阶段的输出正好是这一阶段的前置，跳过某一段往往会在后面某讲突然卡住，届时再回来补齐比按顺序学更费时。

<ConceptDiagram type='layers3' title='阶段二 · 容器与序列 · 知识主线' labels='容器|迭代器|惰性|结果' caption='把 Python 最常用的内置容器用到知其所以然' />

<Callout type="tip" title="怎么用这一阶段" text='先读导览确定出口能力，再逐讲打卡；遇到卡点优先回到对应讲的最小示例，而不是直接翻答案。共 11 讲，合计约 325 分钟。' />

## 阶段能力出口

<CheckList id='L2-goals' title='阶段二 · 容器与序列 · 能力自检' :items='["能独立完成本阶段 11 讲中的全部随堂检测", "能说清 序列协议、list / tuple / dict / set、推导式、迭代器与生成器 各自解决什么问题", "能把本阶段结论接到真实项目并说明代价"]' />

## 讲次地图

| 讲次 | 标题 | 难度 | 建议时长 | 学完能做什么 |
| --- | --- | --- | --- | --- |
| 017 | [序列协议与通用操作](/containers/sequence) | ★★☆☆☆ | 25 分钟 | 理解所有序列共享的一套接口 |
| 018 | [list：动态数组、操作与时间复杂度](/containers/list-basics) | ★☆☆☆☆ | 30 分钟 | 能按成本选择合适操作 |
| 019 | [list 进阶：切片赋值、排序与常见陷阱](/containers/list-advanced) | ★★☆☆☆ | 30 分钟 | 写出正确且高效的列表处理代码 |
| 020 | [tuple 与具名元组：不可变性的价值](/containers/tuple) | ★☆☆☆☆ | 25 分钟 | 知道什么时候该用不可变容器 |
| 021 | [dict：哈希表、视图与插入顺序](/containers/dict-basics) | ★★☆☆☆ | 30 分钟 | 理解字典为什么快、什么时候会退化 |
| 022 | [dict 进阶：默认字典、计数器与合并](/containers/dict-advanced) | ★★☆☆☆ | 25 分钟 | 用标准库容器消灭样板代码 |
| 023 | [set / frozenset：哈希、集合运算与去重](/containers/set) | ★☆☆☆☆ | 25 分钟 | 用集合把成员判断与去重做到 O(1) |
| 024 | [推导式：四种写法与可读性边界](/containers/comprehension) | ★★☆☆☆ | 25 分钟 | 写出简洁且不过度的推导式 |
| 025 | [迭代协议：iterable、iterator 与惰性求值](/containers/iterator) | ★★★☆☆ | 30 分钟 | 能自己实现一个惰性数据源 |
| 026 | [生成器与 yield：send / throw / close](/containers/generator) | ★★★☆☆ | 35 分钟 | 掌握协程的雏形与状态机写法 |
| 027 | [阶段综合：词频统计与内存版 KV](/containers/capstone) | ★★☆☆☆ | 45 分钟 | 用容器与生成器交付一个可测的小工具 |

## 学习节奏建议

<StepBox title='容器与序列 · 前五讲推进节奏' :steps='[{"title": "第 1 步：序列协议与通用操作", "body": "理解所有序列共享的一套接口", "tip": "预计 25 分钟，做完随手打卡"}, {"title": "第 2 步：list：动态数组、操作与时间复", "body": "能按成本选择合适操作", "tip": "预计 30 分钟，做完随手打卡"}, {"title": "第 3 步：list 进阶：切片赋值、排序与", "body": "写出正确且高效的列表处理代码", "tip": "预计 30 分钟，做完随手打卡"}, {"title": "第 4 步：tuple 与具名元组：不可变性", "body": "知道什么时候该用不可变容器", "tip": "预计 25 分钟，做完随手打卡"}, {"title": "第 5 步：dict：哈希表、视图与插入顺序", "body": "理解字典为什么快、什么时候会退化", "tip": "预计 30 分钟，做完随手打卡"}]' />

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先看导览与概念图", "tone": "blue"}, {"title": "逐讲推进", "desc": "跑示例代码并做完随堂检测", "tone": "green"}, {"title": "边界复盘", "desc": "整理易错点与工程代价", "tone": "orange"}, {"title": "进入下一阶段", "desc": "带着出口能力继续", "tone": "purple"}]' direction="horizontal" title='阶段学习闭环' />

## 阶段进度

<ProgressTracker />

[下一阶段：阶段三 · 函数与抽象](/functions/)
