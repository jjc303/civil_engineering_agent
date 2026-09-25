# Agent 层文档

Agent 层确定采用 **FastAPI + LangChain + LangGraph + 工具注册中心 + 状态节点 + MySQL 主存**。Redis 为可选缓存/任务协调组件，Chroma 用于施工规范与项目资料的 RAG 检索。

当前与感知层的边界、数据契约和接口约定见 [跨层集成契约](../integration/CV_Agent_Web_Integration_Contract.md)。

当前实施状态见 [Agent 当前进展报告](Agent_Phase_1_Progress.md)。

Agent 层负责用户请求处理、LangGraph 编排、工具调用、MySQL 业务读写、RAG 检索、统计与报告生成；不负责逐帧视频推理。
