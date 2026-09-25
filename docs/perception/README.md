# 智能建造安全感知系统文档专区 (Perception Docs)

本目录集中管理智慧工地视觉感知、安全帽检测、电子围栏入侵防范系统的设计、规范与实施进展文档：

- [系统当前进展报告 (PROGRESS.md)](./PROGRESS.md)：记录项目当前里程碑状态（阶段 0 已 100% 达成）、已完成的 8 项交付物、单测与冒烟验证数据、原工程平移下线路线以及后续迭代排期。
- [重构实施规格说明书 (Smart_Construction_Refactoring_Plan.md)](./Smart_Construction_Refactoring_Plan.md)：详细的技术规格说明书，包含 Monorepo 拓扑、确定性架构选型（BaseDetector、cv2.pointPolygonTest、纯 Python ByteTrack）、坐标双向映射数学模型、防抖去重生命周期及各阶段量化准入/准出标准（DoD）。
- [原始系统技术总结与深度剖析 (Smart_Construction_Summary.md)](./Smart_Construction_Summary.md)：对 Fork 源项目 `Smart_Construction`（YOLOv5 v2.x 架构、PNPoly 算法、数据集半自动扩增、PyQt5 多线程 GUI 等）的完整架构与业务总结。
- [历史仓库归档元数据 (legacy_meta.json)](./legacy_meta.json)：记录原始 Fork 仓库的 Remote URL、历史 Commit 哈希（`8867a0b`）以及 `.git_archive` 完整备份包索引。
