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
| **状态管理与国际化** | **Pinia + `vue-i18n` + `@vueuse/core`** | 手写全局 EventBus、硬编码多语言分支、窗口 resize 监听 | Pinia 管理语言/字典状态；`vue-i18n` + `<el-config-provider>` 实现简繁热切换与本地持久化 |
| **图标体系** | **Lucide Icons (`lucide-vue-next`)** 或 **`@element-plus/icons-vue`** | 手写切图 / 手写 SVG 拼接 | 现代矢量图标库，支持按需加载与统一尺寸配色 |
| **网络请求与依赖倒置** | **Axios + Port 端口抽象（`api/ports.ts` + `http/` + `mock/`）** | 在基础设施层耦合 UI 弹窗、在业务 API 中散布 `if (isMockEnabled)` | 统一封装超时、409/422/500 通知端口注入、`Accept-Language` 拦截，非 Mock 生产包可完全 Tree-Shaking 剥离 `fixtures.ts` |

---

## 2. 为什么决不手搓？（工程化考量）

1. **规避边界缺陷与性能暗坑**：
   - 围栏标定涉及多边形顶点拖拽、光标变换、射线法碰撞检测、高分屏（Retina）高清渲染。使用 `Konva.js` 可以节约至少 80% 的画布调试时间，且不会产生内存泄露。
2. **保障视觉一致性与交互体验**：
   - 使用 Element Plus 保证全站间距、字体、主题色、过渡动画、表单验证反馈风格统一，呈现专业级工业软件水准。
3. **极大加速交付周期**：
   - 专注于**业务逻辑与契约集成**（如：根据摄像头状态展示监控矩阵、将 Agent 的 Tool Trace 结构化展示在折叠面板中、根据 `source_resolution` 进行坐标正反向缩放转换），而非在“如何写一个弹窗居中”上消耗精力。

---

## 3. 当前前端工程目录结构

```text
web/
├── index.html
├── package.json
├── vite.config.ts
├── tests/                             # 纯 Node TypeScript 单元测试（npm test）
│   ├── register-alias.mjs             # Node ESM @/ 别名解析钩子
│   ├── apiClient.test.ts              # API 通知/翻译端口与拦截器测试（无 UI 依赖）
│   ├── zoneGeometry.test.ts           # 围栏坐标几何与边界钳制测试
│   └── dashboardCharts.test.ts        # 大屏 ECharts Option 纯函数测试
└── src/
    ├── config/runtime.ts              # 环境变量默认值、超时与存储键注册表
    ├── i18n/                          # vue-i18n 简繁词条（zh-CN / zh-HK）、语言探测与策略表
    ├── api/                           # 依赖倒置的接口层
    │   ├── ports.ts                   # ApiNotifier / ApiTranslator 与业务 Port 契约
    │   ├── client.ts                  # 无 UI 依赖的 Axios 实例与拦截器
    │   ├── index.ts                   # HTTP / Mock 组合根（编译期 Tree-Shaking）
    │   ├── http/*.http.ts             # 纯 HTTP 与 SSE 实现
    │   ├── mock/*.mock.ts             # 离线 Mock 适配器
    │   └── notifiers/elementPlus.ts   # Element Plus 消息通知适配器（main.ts 装配）
    ├── composables/                   # 高内聚业务与基础设施 Composables
    │   ├── useCopilotSession.ts       # 助手会话状态机、待确认动作与持久化
    │   ├── useDashboardCharts.ts      # 4 组 ECharts Option 纯构造与主题阈值
    │   ├── useLearningCenter.ts       # 学习中心多域加载与共享任务执行器
    │   ├── useObjectUrl.ts            # Blob URL / 二维码生命周期与自动回收
    │   ├── useSafetyStream.ts         # SSE 实时事件流生命周期与重连
    │   ├── useZoneCanvas.ts           # 围栏画布交互、DPR 自适应与预览探测
    │   └── useZoneDraft.ts            # 围栏未保存草稿缓存读写
    ├── utils/                         # 纯工具模块（datetime.ts / deployment.ts / monitoring.ts / storage.ts / zoneGeometry.ts）
    ├── types/                         # 契约类型（contract.ts / chat.ts）
    ├── stores/                        # Pinia 状态（app.ts / dictionaries.ts / locale.ts）
    ├── components/                    # 公共组件及领域子组件目录（copilot/ / dashboard/ / learning/ / zones/）
    ├── views/                         # 业务容器视图（Dashboard / Violations / RectificationTasks / ZoneEditor / CameraManagement / AgentCopilot / LearningCenter / WorkerLearning，主视图均 < 300 行）
    ├── router/index.ts                # 路由定义与动态页面标题同步
    └── main.ts                        # 应用装配根（Pinia、Router、i18n、Element Plus、ApiNotifier）
```

---

## 4. 相关文档与开发计划
- [Web 控制台当前进展报告](./PROGRESS.md)：阶段里程碑、核心交付物、代码质量与构建验证报告。
- [Web 前端最小闭环开发计划](./Web_Minimal_Closed_Loop_Plan.md)：实施里程碑、MVP 场景、任务拆解与交付时间表。
- [Web 与 Agent 接口约定冻结契约](../integration/Web_Agent_Freeze_Contract.md)：v1.2.0 冻结契约（API 规格、CV 节点调度、MJPEG 预览、严格 Mock 模式与联调门禁）。
- [CV—Agent—Web 协商与集成契约](../integration/CV_Agent_Web_Integration_Contract.md)：三层整体架构与基础协议。
