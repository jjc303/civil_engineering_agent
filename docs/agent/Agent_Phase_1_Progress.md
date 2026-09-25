# Agent 阶段 1 进度

> **日期**：2026-09-25  
> **状态**：最小业务闭环及真实 MySQL 验证完成；待 CV 发布器联调。

## 已完成

1. FastAPI 应用工厂、环境变量配置与 CV 内部 Bearer Token 鉴权。
2. Event Contract v1 的 Pydantic 校验：UUID、UTC 时间、RESOLVED 时间规则、相对 `snapshot_uri`。
3. MySQL/SQLAlchemy 事件与摄像头状态模型；`event_uuid` 为事件主键，重复上报更新同一记录。
4. CV 内部接口：
   - `POST /internal/v1/perception/events`
   - `PUT /internal/v1/perception/cameras/{camera_id}/status`
   - `GET /internal/v1/perception/health`
5. Web/Agent 查询接口：违规列表、统计、摄像头状态、结构化安全查询。
6. 本地工具注册表及 LangGraph 单主流程：`select_tool → execute_tool → format_response`。
7. Alembic 初始迁移：`20260925_0001`。

## 验证结果

`python3 -m pytest -q`：**35 passed**。其中 `tests/agent/test_minimal_closed_loop.py` 覆盖：

- 事件创建、相同 UUID 的升级/闭环更新及统计不重复计数；
- 摄像头运行状态上报和读取；
- LangGraph 工具查询；
- 内部鉴权、绝对媒体路径、无效结案时间的拒绝。

测试使用 SQLite 内存库作为数据库适配层测试替身；它不替代 MySQL 集成验收。

真实 MySQL 已在 WSL `127.0.0.1:3307` 的 `safety_agent` 库完成 `20260925_0001` 迁移。以一个自动清理的测试 UUID 验证了“创建 → 相同 UUID 更新 → LangGraph 按摄像头统计”，结果为单行、`CRITICAL`、计数 `1`。


## 启动与迁移

```bash
python3 -m pip install -r requirements-agent.txt
export AGENT_DATABASE_URL='mysql+pymysql://USER:PASSWORD@HOST:3306/safety_agent?charset=utf8mb4'
export INTERNAL_PERCEPTION_TOKEN='replace-with-random-secret'
alembic upgrade head
uvicorn agent.main:create_app --factory --host 0.0.0.0 --port 8000
```

开发期可临时设置 `AGENT_AUTO_CREATE_SCHEMA=true`，但共享/生产 MySQL 必须使用 Alembic 迁移。

## 下一步联调前置

1. CV 完成 Contract v1 发布器后，以同一 `event_uuid` 推送 `ACTIVE → CRITICAL → RESOLVED`。
2. 确定共享媒体根目录与 Web 的 `snapshot_uri` 映射。
