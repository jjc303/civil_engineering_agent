# 迁移与重构成果文档专区 (Docs / Migration)

本专区汇总了项目从原始 `Smart_Construction` 仓库重构、消化并吸纳进母工程 `civil_engineering_agent` 的**完整系统功能概览、架构原理与快速使用指南**。

---

## 核心文档索引

1. **[系统全功能与使用指南 (SYSTEM_FEATURES_AND_USAGE_GUIDE.md)](./SYSTEM_FEATURES_AND_USAGE_GUIDE.md)**：
   - **架构分层**：感知层 (CV)、智能体层 (Agent)、交互层 (Web/CLI) 的分工与协作契约；
   - **CV 感知子系统全功能**：YOLO 检测、ByteTrack 多相机隔离追踪、人头帽空间拓扑匹配、脚底触地电子围栏判定、单调时钟防抖状态机、违规快照渲染、SQLite Outbox 离线缓冲发布器、无头会话调度器与心跳守护；
   - **Agent 智能体全功能**：FastAPI 服务、MySQL 幂等存储、围栏在线配置管理、LangGraph 认知图与事实接地、DeepSeek 官方大模型适配；
   - **快速使用与操作命令**：无头 CLI 监控运行、日报导出、桌面 GUI 客户端运行、FastAPI 后台启动、全链路端到端集成测试指南；
   - **API 与参数参考**：CLI 参数列表与核心 REST API 规格明细；
   - **测试体系**：全套 52 项自动化测试分类与质量验收基准。

---

## 关联专栏导航

- [系统集成与跨系统联调契约 (`docs/integration/`)](../integration/README.md)
- [安全感知子系统专区 (`docs/perception/`)](../perception/README.md)
- [智能体服务子系统专区 (`docs/agent/`)](../agent/README.md)
