# Web 层开发与技术选型规范

> **核心原则**：**全面拥抱 Vue 3 成熟开源生态，坚持组件化装配，决不自己手搓基础轮子！**  
> 所有通用 UI、图表、画布交互、Markdown 渲染、图标与工具均选用业界高星、高稳定的成熟库，以最高效率交付高质量、高颜值、易维护的工程系统。

---

## 1. 核心技术栈与“绝不手搓”选型清单

| 功能领域 | 选型方案 | 替代的手搓项（严禁手搓） | 选型理由与核心优势 |
|---|---|---|---|
| **核心框架与构建** | **Vue 3 (Composition API / `<script setup>`) + Vite + TypeScript** | 原生 JS / 简易响应式手写 | 极速 HMR、严格静态类型保障，与 Agent 契约模型 100% 对齐 |
| **基础 UI 组件库** | **Element Plus** (或 **Naive UI**) | 手写弹窗、表格、分页器、表单校验、下拉框、加载态等 | 成熟企业级中后台组件库，自带无障碍、主题定制、表单校验及事件闭环 |
| **态势统计图表** | **Apache ECharts + `vue-echarts`** | 手写原生 Canvas/SVG 折线柱状图 | 工业级图表库，开箱即用支持响应式自适应、违规趋势折线图、类型饼图、告警仪表盘 |
| **危险区域多边形标定** | **Konva.js (`vue-konva`)** | 手搓原生 Canvas 像素计算、点选判定、拖拽重绘 | 成熟 2D Canvas 场景图引擎，内置对象树、图层管理、多边形锚点拖拽吸附、视口缩放与事件代理 |
| **智能问答与 Markdown 渲染** | **`markdown-it` + `github-markdown-css` + `highlight.js`** | 手写正则替换 Markdown / 简易富文本 | 完美兼容 GFM 语法、表格、代码高亮、数学公式与防 XSS 注入 |
| **视频流与回放** | **`video.js`** 或 **西瓜播放器 `xgplayer`** | 原生 `<video>` 简陋控制器 | 自带专业播放控制条、截图、全屏、倍速、错误重连及 HLS/HTTP-FLV 扩展能力 |
| **状态管理与通用工具** | **Pinia + `@vueuse/core`** | 手写全局 EventBus、窗口 resize 监听、防抖节流 | Vue 官方推荐状态管理；VueUse 提供开箱即用的传感器、剪贴板、防抖节流 Hooks |
| **图标体系** | **Lucide Icons (`lucide-vue-next`)** 或 **`@element-plus/icons-vue`** | 手写切图 / 手写 SVG 拼接 | 现代矢量图标库，支持按需加载与统一尺寸配色 |
| **网络请求库** | **Axios** (封装统一拦截器与 TS 类型推断) | 原生 `fetch` 裸写 | 统一拦截 401/409/422/500 状态码，自动挂载 Token 与超时取消控制 |

---

## 2. 为什么决不手搓？（工程化考量）

1. **规避边界缺陷与性能暗坑**：
   - 围栏标定涉及多边形顶点拖拽、光标变换、射线法碰撞检测、高分屏（Retina）高清渲染。使用 `Konva.js` 可以节约至少 80% 的画布调试时间，且不会产生内存泄露。
2. **保障视觉一致性与交互体验**：
   - 使用 Element Plus 保证全站间距、字体、主题色、过渡动画、表单验证反馈风格统一，呈现专业级工业软件水准。
3. **极大加速交付周期**：
   - 专注于**业务逻辑与契约集成**（如：根据摄像头状态展示监控矩阵、将 Agent 的 Tool Trace 结构化展示在折叠面板中、根据 `source_resolution` 进行坐标正反向缩放转换），而非在“如何写一个弹窗居中”上消耗精力。

---

## 3. 前端工程典型目录结构

```text
web/
├── index.html
├── package.json
├── vite.config.ts
├── env.d.ts
├── src/
│   ├── assets/              # 静态资源、通用样式 (Tailwind/UnoCSS 或 SCSS)
│   ├── api/                 # 基于契约封装的 API 请求模块 (Axios 实例)
│   │   ├── client.ts        # 统一拦截器、错误码 409 拦截
│   │   ├── violations.ts    # 违规列表与统计接口
│   │   ├── cameras.ts       # 摄像头状态与围栏配置接口
│   │   └── chat.ts          # Agent 智能问答接口
│   ├── types/               # 契约 TypeScript 类型定义 (直接引入 integration 契约)
│   │   └── contract.ts      # 与后端 Pydantic 1:1 严格对齐
│   ├── mock/                # 本地 Mock 桩数据 (VITE_USE_MOCK=true 时生效)
│   │   └── fixtures.ts      # 模拟事件、统计指标与问答响应
│   ├── views/               # 核心业务页面
│   │   ├── Dashboard/       # 安全态势监控大屏 (ECharts 看板)
│   │   ├── Violations/      # 违规事件检索列表与详情弹窗
│   │   ├── ZoneEditor/      # 危险区域多边形标定工具 (基于 Konva.js)
│   │   └── AgentCopilot/    # 智能安全问答助手 (Markdown 对话 + 证据卡片)
│   ├── components/          # 业务复用组件
│   │   ├── VideoPlayer.vue  # 监控播放器封装
│   │   ├── EvidenceCard.vue # 违规抓拍与证据信息卡片
│   │   └── ToolTrace.vue    # 智能体工具调用轨迹展示组件
│   ├── stores/              # Pinia 状态仓储 (相机状态、全局告警、会话缓存)
│   └── main.ts              # 入口文件 (挂载 Element Plus、ECharts、Pinia、Router)
```

---

## 4. 相关文档与开发计划
- [Web 控制台当前进展报告](./PROGRESS.md)：阶段里程碑、核心交付物、代码质量与构建验证报告。
- [Web 前端最小闭环开发计划](./Web_Minimal_Closed_Loop_Plan.md)：实施里程碑、MVP 场景、任务拆解与交付时间表。
- [Web 与 Agent 接口约定冻结契约](../integration/Web_Agent_Freeze_Contract.md)：v1.1.1 冻结契约（API 规格、TS 类型、坐标变换、Mock 规范与联调门禁）。
- [CV—Agent—Web 协商与集成契约](../integration/CV_Agent_Web_Integration_Contract.md)：三层整体架构与基础协议。


