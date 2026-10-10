# 施工安全业务前端

Vue 3、TypeScript、Vite、Element Plus。页面包括现场监控、违规事件、整改任务、区域标定、摄像头与 CV 节点、安全智能助手、学习中心和公开培训答题。

推荐按 [评委快速运行](../docs/REVIEW_QUICKSTART.md) 使用 `python -m scripts.start_review --build`，由 FastAPI 在同一端口提供生产页面和 API。页面使用真实业务数据，默认不启用模拟数据；首次运行空列表是正常状态。旧 `/demo`、`/materials` 仅跳转到 `/dashboard`，独立讲解 Demo 不在项目中。

前端独立开发：安装 Node.js 22.12+，在本目录运行 `npm ci`。将 `.env.example` 复制为 `.env.local`，填写自己的 `VITE_API_BASE_URL`、`VITE_DEV_API_TARGET` 后运行 `npm run dev`。后端的 CORS 也须允许前端开发地址。不要把 API Key 放进任何 `VITE_*` 变量，它们会进入浏览器构建产物。

生产构建执行 `npm run build`。同端口部署应设置 `VITE_API_BASE_URL` 为空、`VITE_USE_MOCK=false`；修改变量后需要重新构建。构建产物在 `web/dist/`，由服务端提供 history 路由回退。`npm run preview` 只用于预览静态构建，并不自动启动业务后端。
