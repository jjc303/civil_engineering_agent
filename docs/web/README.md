# Web 层文档

Web 层通过 FastAPI 提供的 API 与 WebSocket 获取摄像头状态、违规事件、证据媒体和报告任务结果。

Web 层不直接读取 CV 本地 SQLite 文件、不访问模型进程内部状态，也不直接操作 MySQL 表；所有读写均经 Agent API。跨层接口约定见 [CV—Agent—Web 协商与集成契约](../integration/CV_Agent_Web_Integration_Contract.md)。
