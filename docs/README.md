# 项目技术文档中心 (Docs)

本目录汇总了 **Civil Engineering Agent (智能建造工程智能体)** 各子系统与核心模块的技术设计、规格说明与实施进展：

## 1. 子系统专栏

- [安全感知子系统 (Perception)](./perception/README.md)
  - [系统当前进展报告 (PROGRESS.md)](./perception/PROGRESS.md)：最新 v4.0 版本，涵盖阶段 0~2、跨系统契约冻结、Outbox 机制、代码治理及测试分类。
  - [重构实施规格说明书 (Smart_Construction_Refactoring_Plan.md)](./perception/Smart_Construction_Refactoring_Plan.md)：包含阶段 0 门禁、确定性架构选型、坐标双向映射数学模型、防抖去重生命周期及各阶段量化验收标准（DoD）。
  - [原始系统技术总结与深度剖析 (Smart_Construction_Summary.md)](./perception/Smart_Construction_Summary.md)：原 Fork 项目的完整架构、算法原理与评测指标剖析。
  - [历史仓库归档元数据 (legacy_meta.json)](./perception/legacy_meta.json)：原始仓库 Commit `8867a0b` 完整 Git Bundle 归档索引。

- [系统集成与联调契约 (Integration)](./integration/README.md)
  - [CV—Agent—Web 协商与集成契约 (CV_Agent_Web_Integration_Contract.md)](./integration/CV_Agent_Web_Integration_Contract.md)：定义统一违规事件协议 (Contract v1)、时间锚点 (TimeAnchor)、相机状态上报、电子围栏格式、内部 API 与端到端联调门禁。

- [智能体服务子系统 (Agent)](./agent/README.md)
  - [Agent 阶段一进展报告 (Agent_Phase_1_Progress.md)](./agent/Agent_Phase_1_Progress.md)：涵盖 FastAPI 服务、工具注册、MySQL 幂等存储与 LangGraph 状态编排。

## 2. 文档组织架构

```text
docs/
├── README.md                      # 文档中心总览与主导航
├── integration/                   # 跨系统集成契约专区
│   ├── README.md
│   └── CV_Agent_Web_Integration_Contract.md # 统一通信与生命周期契约
├── agent/                         # Agent 智能体系统专区
└── perception/                    # 视觉安全感知子系统专区
    ├── README.md                  # 感知专区目录导航
    ├── PROGRESS.md                # 阶段进展与现状报告 (v4.0 持续更新)
    ├── Smart_Construction_Refactoring_Plan.md # 详细实施规格说明书
    ├── Smart_Construction_Summary.md          # 原始工程技术剖析
    └── legacy_meta.json           # 历史 Git 归档元数据
```
