# Agent 最小闭环实施计划

> **版本**：v0.1  
> **目标**：优先交付“CV 事件进入 FastAPI，经幂等校验写入 MySQL，可由工具和 LangGraph 查询并返回统计结果”的最小业务闭环。  
> **范围基线**：FastAPI + LangChain + LangGraph + 工具注册 + 显式状态节点 + MySQL 主存。Redis 和 Chroma 仅预留，不进入 v0.1 的运行时关键路径。

## 1. 最小闭环定义

```text
CV Event Contract v1
  ↓ POST /internal/v1/perception/events
FastAPI + Pydantic 校验
  ↓ event_uuid 幂等 Upsert
MySQL violation_events
  ↓ Repository / Tool Registry
LangGraph 单一主流程
  ↓
违规查询、统计摘要或 Web API 响应
```

### v0.1 必须完成

1. 接收并校验 `SafetyViolationEventV1`。
2. 以 `event_uuid` 为唯一键向 MySQL 幂等创建/更新事件。
3. 查询违规事件、按类型/严重级别聚合统计、查询摄像头最新状态。
4. 注册 `query_violations`、`get_violation_statistics`、`get_camera_status` 三个工具。
5. 使用 LangGraph `StateGraph` 实现一个单一、显式状态的查询图。
6. 提供可由 CV 使用的内部事件与状态上报 API。
7. 用 MySQL 集成测试证明“重复上报不重复计数”。

### v0.1 明确不做

- 真正的 LLM 对话和模型供应商接入；图先使用确定性意图/参数路由，后续再把 LLM 节点插入图中。
- Redis、Celery、分布式任务队列。
- Chroma 建库、文件上传与 RAG；只保留接口位置。
- 用户登录、RBAC、外部 OAuth。
- Web 前端页面、RTSP 调度、CV 模型推理。
- 在 MySQL 中存储图片或视频二进制。

## 2. 责任边界

| 组件 | v0.1 责任 |
|---|---|
| CV | 发出 Event Contract v1、上报状态、以 `event_uuid` 进行重试；不连接 MySQL |
| Agent API | 校验、幂等 Upsert、查询、工具注册、LangGraph 查询图、返回结构化结果 |
| MySQL | 事件与摄像头状态的唯一业务事实来源 |
| Web | 仅消费公开查询 API；v0.1 可使用 OpenAPI/fixture 验证，不要求页面 |

跨层字段、时间与媒体约定以 [CV—Agent—Web 协商与集成契约](../integration/CV_Agent_Web_Integration_Contract.md) 为准。

## 3. 技术决策

| 领域 | v0.1 决策 | 原因 |
|---|---|---|
| HTTP | FastAPI + Pydantic v2 | 契约校验、OpenAPI 与依赖注入 |
| 数据库访问 | SQLAlchemy 2.x + PyMySQL，同步 Repository | 一周交付优先，代码直接、MySQL 兼容稳定 |
| Schema 迁移 | Alembic | MySQL 表结构可追踪、可复现 |
| Agent 编排 | LangGraph `StateGraph` | 显式状态、可测试、后续可插入 LLM/RAG 节点 |
| 工具定义 | LangChain tool + 本地工具注册表 | 保持 LangChain 工具兼容，避免图直接写 SQL |
| 内部 CV 鉴权 | 静态 Bearer Token（环境变量） | 最小可用；生产期改为服务身份和密钥轮换 |
| 媒体 | 仅保存 `snapshot_uri` | 媒体放共享卷/对象存储，MySQL 只存引用 |
| Redis/Chroma | Protocol 和配置预留，不实例化 | 避免延迟最小闭环 |

## 4. 推荐目录结构

```text
agent/
├── __init__.py
├── main.py                         # FastAPI application factory
├── core/
│   ├── config.py                   # 环境变量与 Settings
│   └── security.py                 # 内部 Bearer Token 校验
├── contracts/
│   ├── event_v1.py                 # CV Event Contract v1
│   ├── camera.py                   # 摄像头状态与配置 DTO
│   └── query.py                    # 查询与统计 DTO
├── db/
│   ├── base.py                     # SQLAlchemy Base / engine / session
│   ├── models.py                   # ORM 表模型
│   └── migrations/                 # Alembic 迁移
├── repositories/
│   └── violations.py               # MySQL 幂等 Upsert 与查询
├── services/
│   └── perception_service.py       # API 层业务编排
├── tools/
│   ├── registry.py                 # 工具注册表
│   └── safety_tools.py             # 查询、统计、状态工具
├── graph/
│   ├── state.py                    # TypedDict / Pydantic 图状态
│   ├── nodes.py                    # 确定性节点
│   └── safety_graph.py             # StateGraph 编译入口
└── api/
    ├── internal_perception.py      # CV 内部接口
    └── public_safety.py            # Web / Agent 查询接口

tests/agent/
├── test_event_contract.py
├── test_event_repository.py
├── test_internal_perception_api.py
├── test_public_safety_api.py
└── test_safety_graph.py
```

## 5. 数据与 MySQL 模型

### 5.1 `violation_events`

`event_uuid` 是主键/唯一键，所有事件更新均以它为条件。建议字段：

```text
event_uuid               CHAR(36) PRIMARY KEY
schema_version           VARCHAR(16) NOT NULL
camera_id                VARCHAR(128) NOT NULL
monitor_session_id       VARCHAR(128) NOT NULL
track_id                 BIGINT NOT NULL
violation_type           VARCHAR(64) NOT NULL
severity                 VARCHAR(32) NOT NULL
status                   VARCHAR(32) NOT NULL
zone_id                  VARCHAR(128) NULL
zone_name                VARCHAR(255) NULL
occurred_at_utc          DATETIME(6) NOT NULL
resolved_at_utc          DATETIME(6) NULL
duration_seconds         DECIMAL(12, 3) NOT NULL
snapshot_uri             VARCHAR(1024) NULL
model_name               VARCHAR(128) NULL
model_version            VARCHAR(128) NULL
extra_details            JSON NOT NULL
created_at_utc           DATETIME(6) NOT NULL
updated_at_utc           DATETIME(6) NOT NULL
```

索引：`(camera_id, occurred_at_utc)`、`(status, occurred_at_utc)`、`(severity, occurred_at_utc)`、`(violation_type, occurred_at_utc)`。

### 5.2 `camera_statuses`

每个摄像头仅保留一条最新状态，使用 `camera_id` 唯一键：

```text
camera_id, monitor_session_id, is_online, fps, processed_frame_id,
active_workers_count, model_name, model_version, reported_at_utc, extra_details
```

摄像头元数据和围栏配置表不是 v0.1 阻塞项；如 CV 需要真实配置下发，在 v0.2 增加 `cameras`、`danger_zones`、`danger_zone_versions`。

## 6. API 契约

### 6.1 CV 内部接口

| 方法 | 路径 | 鉴权 | 成功响应 |
|---|---|---|---|
| `POST` | `/internal/v1/perception/events` | Bearer Token | `200`，`CREATED` 或 `UPDATED` |
| `PUT` | `/internal/v1/perception/cameras/{camera_id}/status` | Bearer Token | `200` |
| `GET` | `/internal/v1/perception/health` | Bearer Token | `200` |

事件成功响应：

```json
{
  "event_uuid": "a5d10bde-ef52-4ef7-8471-50b74c864623",
  "operation": "CREATED",
  "status": "ACTIVE",
  "server_received_at_utc": "2026-09-25T10:30:01Z"
}
```

错误语义：

- `401/403`：鉴权错误，CV 不自动重试。
- `422`：契约错误，CV 不自动重试，写入本地错误日志。
- `429/5xx` 或网络超时：CV Outbox 指数退避重试。

### 6.2 Web / Agent 查询接口

| 方法 | 路径 | 目的 |
|---|---|---|
| `GET` | `/api/v1/violations` | 按摄像头、时间、类型、严重级别、状态分页查询 |
| `GET` | `/api/v1/violations/statistics` | 返回总数、类型分布、严重级别分布、平均时长 |
| `GET` | `/api/v1/cameras/{camera_id}/status` | 返回最新 CV 状态 |
| `POST` | `/api/v1/agent/safety-query` | 调用 LangGraph 查询图，返回结构化摘要 |

## 7. 工具与 LangGraph 最小实现

工具注册表首先提供：

```text
query_violations(camera_id?, start_time?, end_time?, severity?, status?)
get_violation_statistics(start_time?, end_time?, camera_id?)
get_camera_status(camera_id)
```

`StateGraph` 采用单主流程：

```text
validate_request → select_tool → execute_tool → format_response → END
```

v0.1 使用显式 `operation` 参数，例如 `violations`、`statistics`、`camera_status`，确保无需 LLM API Key 也能端到端验证。未来节点可在 `select_tool` 前加入 LangChain 模型意图提取和 Chroma 检索，但不能破坏既有工具输入输出。

## 8. 实施顺序与验收

### Sprint A：可持久化事件 API

1. 创建 `agent/` 目录和 Settings。
2. 添加 FastAPI、SQLAlchemy、PyMySQL、Alembic、LangChain、LangGraph、Uvicorn、HTTPX 依赖。
3. 创建 Event Contract v1 与 MySQL ORM/migration。
4. 实现内部事件 Upsert、摄像头状态 Upsert、健康检查。
5. 编写 MySQL 集成测试。

**验收**：同一 `event_uuid` 连续提交 3 次，只产生 1 行，最后状态、严重级别和时长正确。

### Sprint B：查询与图编排

1. 实现 Repository 查询和统计。
2. 实现公开查询 API。
3. 实现工具注册表与三个安全工具。
4. 实现确定性 LangGraph 查询图。
5. 编写 API/Graph 测试。

**验收**：固定事件 fixture 可经 FastAPI 写入、查询、统计，并由 LangGraph 返回同一统计结论。

### Sprint C：CV 联调

1. 使用 CV 的 `sample_walk.mp4` 生成完整事件链。
2. CV 发布器向内部 API 重放该事件链。
3. 验证 ACTIVE → CRITICAL → RESOLVED 在同一 `event_uuid` 上更新。
4. 验证 `snapshot_uri` 可被 Web 媒体路径解析。

**验收**：端到端联调脚本无需人工修改数据库即可通过。

## 9. 前置条件与风险

| 项目 | 当前状态 | 处理方式 |
|---|---|---|
| MySQL 实例与连接串 | 未提供 | 使用 `AGENT_DATABASE_URL` 环境变量；未配置时应用拒绝启动生产模式 |
| CV Event Contract v1 发布器 | CV 计划实现 | Agent 先用 JSON fixture 和 HTTPX 测试客户端开发 |
| 媒体共享目录 | 未确定 | v0.1 只验证 URI 格式；部署时配置 `MEDIA_ROOT`/`MEDIA_BASE_URL` |
| 内部鉴权 Token | 未提供 | 使用 `INTERNAL_PERCEPTION_TOKEN` 环境变量；测试使用固定临时值 |
| Redis / Chroma | 未接入 | 不阻塞 v0.1，保留配置命名空间与接口位置 |

## 10. 完成定义（DoD）

最小闭环完成必须同时满足：

1. MySQL migration 可从空库重复执行。
2. Event Contract v1 的合法、非法、重复请求均有测试。
3. Event Upsert、状态 Upsert、查询、统计 API 通过集成测试。
4. `event_uuid` 幂等、UTC 时间、`snapshot_uri` 相对路径规则已验证。
5. LangGraph 不依赖 LLM API Key 即可通过工具返回结构化安全摘要。
6. CV 固定视频事件链可通过 HTTP 接口完整重放。
7. Redis、Chroma、Web 页面和监控启动调度未被伪装为已完成能力。
