import { defineConfig } from 'vitepress'

// GitHub 项目页部署在子路径下，base 与仓库名一致。
// 改用自定义域名 / 用户主页仓库时，构建时传 VP_BASE=/ 即可，无需改代码。
const BASE = process.env.VP_BASE || '/python/'

// 站点身份信息集中在这里，课程定稿后改这些常量即可。
const SITE_TITLE = 'Python 零基础通关'
const SITE_DESC = '一套为完全零基础学习者设计的交互式 Python 教程：递进式知识路径 + 分类分级的工程实战。'

export default defineConfig({
  lang: 'zh-CN',
  title: SITE_TITLE,
  description: SITE_DESC,
  base: BASE,
  outDir: '.vitepress/dist',
  cacheDir: '.vitepress/cache',
  lastUpdated: true,
  cleanUrls: true,
  ignoreDeadLinks: true,
  metaChunk: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${BASE}favicon.svg` }],
    ['meta', { name: 'theme-color', content: '#3776ab' }],
    ['meta', { name: 'og:title', content: `${SITE_TITLE} · 交互式教程` }],
    ['meta', { name: 'og:description', content: SITE_DESC }],
  ],
  vite: {
    build: {
      // 本地全文搜索索引只在打开搜索框时懒加载；提高阈值避免构建时输出无害的体积提示。
      chunkSizeWarningLimit: 5000,
    },
  },
  markdown: {
    lineNumbers: true,
    container: {
      tipLabel: '小贴士',
      warningLabel: '注意',
      dangerLabel: '当心',
      infoLabel: '说明',
      detailsLabel: '展开查看详情',
    },
    // 允许组件属性里的 < 与 > 原样输出（组件用法讲解会用到）
    html: true,
  },
  themeConfig: {
    logo: '/favicon.svg',
    siteTitle: SITE_TITLE,
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一节', next: '下一节' },
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '课程目录',
    returnToTopLabel: '回到顶部',
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索课程', buttonAriaLabel: '搜索课程' },
          modal: {
            noResultsText: '没有找到相关内容',
            resetButtonTitle: '清除搜索',
            backButtonTitle: '返回',
            displayDetails: '展开详情',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },
    // 栏目结构为占位骨架；下拉菜单的形态与参考站点 main 分支保持一致，
    // 课程定稿后把 nav / sidebar 的条目换成真实讲次即可。
    nav: [
      { text: '学习路线', link: '/guide/' },
      {
        text: '阶段课程',
        items: [
          { text: '阶段课程导览', link: '/foundation/' },
          { text: '工程实战', link: '/projects/' },
        ],
      },
      { text: '练习与速查', link: '/practice/' },
      { text: '关于', link: '/about/' },
    ],
    sidebar: {
      '/guide/': placeholderSidebar('开始之前', [
        { text: '学习路线', link: '/guide/' },
      ]),
      '/foundation/': placeholderSidebar('阶段课程', [
        { text: '阶段课程导览', link: '/foundation/' },
      ]),
      '/projects/': placeholderSidebar('工程实战', [
        { text: '工程场景地图', link: '/projects/' },
      ]),
      '/practice/': placeholderSidebar('练习与速查', [
        { text: '练习与速查', link: '/practice/' },
      ]),
      '/about/': placeholderSidebar('关于本站', [
        { text: '关于本站', link: '/about/' },
        { text: '本地运行与 Pages 部署', link: '/about/deploy' },
      ]),
    },
    socialLinks: [{ icon: 'github', link: 'https://github.com/lfire/python' }],
    footer: {
      message: '为完全零基础的学习者而写 · 站点框架与交互组件先行，课程内容陆续补充',
      copyright: '© 2026 Python 零基础通关',
    },
  },
})

/**
 * 占位侧栏。写正文时把 items 换成真实讲次即可；
 * 需要按阶段分组时，返回多个 { text, collapsed, items } 对象。
 */
function placeholderSidebar(group: string, items: { text: string; link: string }[]) {
  return [{ text: group, collapsed: false, items }]
}
