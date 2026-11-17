# 前端架构解耦与组件拆分待办计划（TODO）

> 本计划沉淀了在简繁切换改造前对 `web/src/` 体检发现的**第 4、5 项独立架构技术债**（API 层依赖倒置与 Mock 注入解耦、大体积上帝组件拆分与样式收敛），供后续排期实施，避免与功能迭代耦合产生回归风险。

---

## 一、API 基础设施层解耦（解决第 4 项：违反 DIP / OCP）

### 现状问题

1. **基础设施层反向依赖 UI 框架（违反 DIP 依赖倒置原则）**
   - `web/src/api/client.ts` 直接引入并调用 `element-plus` 的 `ElMessage.error` / `ElMessage.warning` 弹出全局提示。
   - **后果**：HTTP 客户端无法在无 UI 环境或纯 Node 单元测试中独立运行；未来若需统一替换提示策略（如改用通知栏、去重弹窗或按页面静默处理），必须直接修改底层 Axios 拦截器。

2. **Mock 逻辑硬编码在各个 API 模块函数内（违反 OCP / 单一职责）**
   - `web/src/api/cameras.ts`、`web/src/api/violations.ts`、`web/src/api/zones.ts`、`web/src/api/chat.ts`、`web/src/api/cameraManagement.ts`、`web/src/api/rectificationTasks.ts` 中均直接分散着 `if (isMockEnabled) { ... }` 分支判断。
   - **后果**：真实 HTTP 请求逻辑与离线演示数据逻辑耦合在一起，Mock 数据也会随业务 API 一并进入主路径代码结构。

### 目标架构与改造方案

1. **引入通知端口抽象（`NotifierPort`）**
   - 新增 `web/src/api/ports.ts`（定义 `ApiNotifier` 接口：`notifyError(message)`、`notifyWarning(message)`、`notifyConflict(message)`）。
   - `api/client.ts` 仅持有可注入的 `notifier` 引用（默认空实现或通过 `registerApiNotifier(...)` 在 `main.ts` 装配阶段绑定 Element Plus 实现），彻底解除 HTTP 客户端对 UI 组件库的静态依赖。

2. **引入仓储/适配器工厂（`Repository / Transport Adapter`）**
   - 为摄像头、违规、区域、问答、整改等模块定义接口契约（Port），拆分 `*.http.ts` 与 `*.mock.ts` 两个独立实现；
   - 在 `web/src/api/index.ts`（组装根 / Composition Root）根据 `VITE_USE_MOCK` 一次性选择注入 HTTP 适配器或 Mock 适配器；
   - 配合 Vite Tree-Shaking，生产非 Mock 构建可彻底剥离 `mock/fixtures.ts` 体积。

---

## 二、大体积视图组件拆分与样式收敛（解决第 5 项：违反 SRP / 高内聚）

### 现状问题

| 文件 | 规模 | 职责混杂与可维护性问题 |
| --- | --- | --- |
| `web/src/views/AgentCopilot.vue` | ~705 行 | 单组件同时管理：对话消息状态机、4 个业务对话框（报告详情、培训详情、整改创建、培训参数设置）、`sessionStorage` 会话持久化、二维码 Blob URL 释放，以及通过拼接自然语言句触发后台写操作。 |
| `web/src/views/ZoneEditor.vue` | ~781 行 | Canvas 几何坐标投影/顶点拖拽渲染、MJPEG 实时/单帧分辨率探测、`localStorage` 草稿保存与围栏表单配置全部耦合在同一文件；存在默认 `1920x1080` 坐标魔数及未使用的死代码 `scaleRatioText`。 |
| `web/src/views/LearningCenter.vue` | 单文件混杂 5 域 | 在同一文件内编排本周概览、AI 教育建议、推荐案例/文档库搜索、培训任务与 5 个复杂表单弹窗，模板单行高度嵌套、可读性差。 |
| `web/src/views/Dashboard.vue` | ~470 行 | 混杂 SSE 订阅与防抖、摄像头分页逻辑及 4 组 ECharts 配置；`<style scoped>` 末尾累计存在三层历史覆盖样式补丁。 |

### 目标拆分方案

1. **`AgentCopilot.vue` 拆分为容器 + 组合式状态 + 独立弹窗子组件**
   - `web/src/composables/useCopilotSession.ts`：封装消息列表、`sessionStorage` 读写、对话 ID 管理与等待计时器。
   - `web/src/components/copilot/ReportDetailDialog.vue`、`TrainingDetailDialog.vue`、`RectificationCreateDialog.vue`、`TrainingSetupDialog.vue`：各弹窗自治校验与提交事件；且整改创建建议优先对接结构化 `proposeRectificationTaskCreate` 接口，逐步淘汰脆弱的自然语言拼接触发方式。

2. **`ZoneEditor.vue` 拆分画布交互引擎与业务配置**
   - `web/src/composables/useZoneCanvas.ts`：纯粹负责 DPR 自适应缩放、像素坐标投影、顶点命中测试与拖拽绘制。
   - `web/src/composables/useZoneDraft.ts`：封装草稿自动保存与恢复（并与存储键注册表收口）。
   - `web/src/components/zones/ZoneConfigPanel.vue`：抽离右侧参数配置表单与区域列表；清理死代码 `scaleRatioText` 与重复坐标魔数。

3. **`LearningCenter.vue` 按业务域模块化**
   - 拆出 `ReportDetailDialog.vue`、`TrainingEditorDialog.vue`、`DocumentDetailDialog.vue`、`DocumentUploadDialog.vue` 与 `LearningOverviewCard.vue`，并将二维码 Blob URL 创建与释放封装为 `useObjectUrl` Composable，杜绝内存泄漏遗漏。

4. **`Dashboard.vue` 拆分图表工厂与实时数据流**
   - `web/src/composables/useDashboardCharts.ts`：封装 4 个 ECharts `Option` 构建纯函数，使 `Dashboard.vue` 只关注布局与状态绑定。
   - `web/src/composables/useSafetyStream.ts`：封装 SSE 断线状态与统计防抖刷新。
   - 清理 `<style scoped>` 末尾三层叠加补丁，合并为单一清晰的 BEM/语义样式定义。

---

## 三、验收标准（后续执行本 TODO 时对照）

- [ ] `web/src/api/` 目录下不再出现 `element-plus` 导入及散落的 `if (isMockEnabled)` 分支。
- [ ] 上述 4 个主视图文件各自收敛至 **300 行以内**，且每个弹窗/画布交互可单独进行类型检查与单元测试。
- [ ] 执行 `cd web && npm run build` 零告警通过，全站核心流程（监控、事件、标定、助手、学习中心）功能回归一致。
