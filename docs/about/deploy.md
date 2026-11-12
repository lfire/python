---
title: 本地运行与 GitHub Pages 部署
description: 如何在本地预览、构建，以及推送后由 GitHub Actions 自动部署到 Pages。
---

# 本地运行与 GitHub Pages 部署

本站是一个标准的 VitePress 静态站点，源码在 `docs/`，构建产物在 `docs/.vitepress/dist/`。**不需要数据库、不需要服务端、不需要密钥**。

## 目录结构

```text
python/                        # 仓库根目录
├── docs/                      # VitePress 源码
│   ├── .vitepress/
│   │   ├── config.mts         # 站点配置（base / 导航 / 侧栏）
│   │   ├── components/        # 交互组件（27 个，其中 24 个全局注册 + StepLab 别名）
│   │   ├── theme/             # 自定义主题与 CSS
│   │   ├── richtext.ts        # 组件属性里的最小 Markdown 解析
│   │   └── utils.ts           # 学习进度存储（localStorage）
│   ├── index.md               # 首页
│   ├── guide/ foundation/ projects/ practice/ about/   # 骨架占位页，课程目录待补充
│   └── public/favicon.svg
├── .github/workflows/deploy.yml   # Pages 自动部署
├── package.json
└── package-lock.json
```

## 本地开发

```bash
npm install
npm run dev          # 启动开发服务器，默认 http://localhost:5173/python/
```

其他常用命令：

```bash
npm run build        # 构建静态站点到 docs/.vitepress/dist/
npm run preview      # 本地预览构建产物
```

<Callout type="tip" title="改了交互组件没生效？" text="修改 .vitepress/components/ 下的 .vue 文件后，若开发服务器没有热更新，重启一次 npm run dev 即可。构建产物是纯静态文件，浏览器端不需要 Node。" />

## 部署到 GitHub Pages

仓库已配置好工作流 `.github/workflows/deploy.yml`，流程是：

```text
push 到 main
   → actions/checkout 拉代码（fetch-depth: 0，供 lastUpdated 使用）
   → setup-node + npm ci
   → npm run build（生成 docs/.vitepress/dist/）
   → actions/configure-pages + upload-pages-artifact
   → actions/deploy-pages 发布
```

### 首次启用只需做一次

1. 打开仓库的 **Settings → Pages**。
2. 在 **Build and deployment → Source** 里选择 **GitHub Actions**（不是 "Deploy from a branch"）。
3. 推送代码到 `main` 分支，Actions 会自动跑完并给出站点地址。

部署完成后，站点地址为：

```text
https://lfire.github.io/python/
```

<Callout type="warn" title="base 必须和仓库名一致" text="config.mts 里 base = '/python/' 对应仓库名 python。如果改了仓库名、或改用自定义域名／用户主页仓库，必须同步修改 base，否则页面的 CSS / JS 会 404。" />

修改方式（二选一）：

- 直接改 `docs/.vitepress/config.mts` 里的 `const BASE`；
- 或在构建时通过环境变量注入：`VP_BASE=/ npm run build`（适用于自定义域名根路径）。

## 自定义域名（可选）

1. 在 `docs/public/` 下放一个名为 `CNAME` 的文件，内容只有一行你的域名。
2. 在域名服务商处添加 CNAME 记录指向 `lfire.github.io`。
3. 在 Settings → Pages → Custom domain 填入同一域名，并建议开启 Enforce HTTPS。
4. 把 base 改成 `/`（`VP_BASE=/` 或直接改配置常量）后重新部署。

## 常见问题

| 现象 | 检查 |
| --- | --- |
| 页面能开但样式全丢 | `base` 与仓库名不匹配，或 Pages 的 Source 选错了 |
| Actions 报 `npm ci` 失败 | 提交时记得带上 `package-lock.json` |
| 中文文件名/路径 404 | VitePress 会自动处理，检查是否用了未提交的本地文件 |
| 交互按钮点了没反应 | 浏览器禁用了 JavaScript，或构建产物不完整；重新 `npm run build` |
| 搜索结果不全 | 本地搜索索引在构建时生成，新增页面后需重新构建部署 |
| 打卡进度串到别的教程站 | `utils.ts` 里的 localStorage 键名要按站点区分，见下表 |

## 换站点身份要改哪几处

| 内容 | 位置 |
| --- | --- |
| 站点标题 / 描述 / 主题色 / GitHub 链接 | `docs/.vitepress/config.mts` |
| 品牌色数值（浅色与深色两套） | `docs/.vitepress/theme/custom.css` 顶部 `:root` 与 `.dark` |
| favicon | `docs/public/favicon.svg` |
| 首页文案与能力介绍 | `docs/.vitepress/components/HomePage.vue` |
| 课程页面清单 / 阶段定义 | `docs/.vitepress/utils.ts` |
| 代码块「在线运行」目标 | `docs/.vitepress/theme/index.ts` 的 `RUN_TARGETS` |
| 进度存储键名（同域名下必须唯一） | `docs/.vitepress/utils.ts` 的 `KEY` / `CHECK_KEY` |

<Callout type="idea" title="内容维护" text="新增一页只要在 docs/ 下加 .md 文件，并在 .vitepress/config.mts 的侧栏里补一条；如果希望它计入学习进度，再在 .vitepress/utils.ts 的 LESSONS 数组里加一项即可。首页的路线图、场景矩阵、概念图与进度汇总都从这些数据读取。" />

[返回关于本站 →](/about/)
