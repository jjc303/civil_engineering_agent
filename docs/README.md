# 项目技术文档中心 (Docs)

本目录汇总了 **Civil Engineering Agent (智能建造工程智能体)** 各子系统与核心模块的技术设计、规格说明与实施进展：

## 1. 子系统专栏

- [安全感知子系统 (Perception)](./perception/README.md)
  - [系统当前进展报告 (PROGRESS.md)](./perception/PROGRESS.md)：阶段 0 完成情况（100% 达成）、已交付模块清单、测试验证数据及后续迭代排期。
  - [重构实施规格说明书 (Smart_Construction_Refactoring_Plan.md)](./perception/Smart_Construction_Refactoring_Plan.md)：包含阶段 0 门禁、确定性架构选型、坐标双向映射数学模型、防抖去重生命周期及各阶段量化验收标准（DoD）。
  - [原始系统技术总结与深度剖析 (Smart_Construction_Summary.md)](./perception/Smart_Construction_Summary.md)：原 Fork 项目的完整架构、算法原理与评测指标剖析。
  - [历史仓库归档元数据 (legacy_meta.json)](./perception/legacy_meta.json)：原始仓库 Commit `8867a0b` 完整 Git Bundle 归档索引。

## 2. 文档组织架构

```text
docs/
├── README.md                      # 文档中心总览与主导航
└── perception/                    # 视觉安全感知子系统专区
    ├── README.md                  # 感知专区目录导航
    ├── PROGRESS.md                # 阶段进展与现状报告 (持续更新)
    ├── Smart_Construction_Refactoring_Plan.md # 详细实施规格说明书
    ├── Smart_Construction_Summary.md          # 原始工程技术剖析
    └── legacy_meta.json           # 历史 Git 归档元数据
```
