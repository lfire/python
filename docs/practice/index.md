---
title: 练习与速查
description: 综合自测、语法速查、常见坑、FAQ、面试自评、生态地图与术语表。
---

# 练习与速查

这里是全站的横向工具区：不按讲次组织，而是按「查什么、练什么、怎么自评」组织。

- [语法与标准库速查表](/practice/cheatsheet) — 按主题整理的语法、内置函数、标准库与命令行速查
- [常见坑与反模式](/practice/pitfalls) — 可变默认参数、延迟绑定、浮点精度、GIL 误解等高频事故
- [零基础常见问题](/practice/faq) — 环境、版本、编码、性能、依赖与调试的常见疑问
- [面试与能力自评](/practice/interview) — 分阶段能力矩阵、高频考点与自测题
- [Python 生态与选型地图](/practice/ecosystem) — 按领域整理的主流库、选型维度与版本现状
- [术语表](/practice/glossary) — 全站出现的术语按字母与主题索引

<ProgressTracker />

## 综合自测

<Quiz no="P-1" q="一个函数把可变列表作为默认参数，连续调用两次，最可能发生什么？" :options='["第二次调用会复用第一次留下的列表状态", "Python 会直接抛出 TypeError", "每次调用都会自动深拷贝默认值", "默认值会在函数结束时被垃圾回收"]' answer="0" explain="默认值在定义时求值一次，可变对象会被所有调用共享。应改用 None 作哨兵。" />

<Predict no="P-2" q="下面代码的输出是什么？" :options='["True False", "True True", "False False", "报错"]' answer="0" output="True False" explain="0.1 + 0.2 在二进制浮点下不精确等于 0.3，但 isclose 会判定近似相等。" />

<FillBlank no="P-3" tpl="用 0.1 + 0.2 与 0.3 比较时，应该用 math.___ 判断近似相等" :answers='["isclose"]' hint="math 模块里用于近似比较的函数" explain="浮点误差来自二进制表示，比较应带容差。" />
