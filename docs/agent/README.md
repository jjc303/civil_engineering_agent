# Agent 层文档

Agent 层当前采用 **FastAPI + LangChain + LangGraph + 工具注册中心 + 状态节点 + MySQL 主存**。当前已上线范围不包含会话记忆、Chroma、资料上传或 RAG；`conversation_id` 也尚未形成持久会话上下文。首版会话记忆与资料知识库的实施、运维和验收以 [Agent 会话记忆与 RAG 向量库管理规范](Agent_Memory_RAG_Management.md) 为唯一准绳。

当前与感知层的边界、数据契约和接口约定见 [跨层集成契约](../integration/CV_Agent_Web_Integration_Contract.md)。

当前实施状态见 [Agent 当前进展报告](Agent_Phase_1_Progress.md)。

Agent 层当前负责用户请求处理、LangGraph 编排、工具调用、MySQL 业务读写、统计与报告生成；不负责逐帧视频推理。RAG 检索将在上述规范完成验收后接入。
