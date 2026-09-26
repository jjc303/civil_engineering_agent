# CV—Agent—Web 协商与集成契约

> **版本**：v1.2 (Phase 2 已实现)
> **状态**：Agent HTTP 调度、CV 节点心跳与 Agent 代理 MJPEG 已实现。
> **适用范围**：`perception/` 感知层、Agent/FastAPI 服务与 Web 前端。  
> **文档优先级声明**：Web–Agent 之间的具体 HTTP API、数据结构、前端类型与联调标准**统一以 [Web_Agent_Freeze_Contract.md](./Web_Agent_Freeze_Contract.md) (v1.2.0+) 为最终准绳**。


## 1. 目标与基本原则

```text
视频流 / 图片
  ↓
CV：检测 → 拓扑匹配 → 追踪 → 状态机 → 违规事件
  ↓ HTTPS 内部事件接口（幂等）
Agent API：FastAPI → 校验 → MySQL
  ├── LangGraph 工具调用
  └── Web API / WebSocket
```

1. **MySQL 是生产环境唯一业务主存**；SQLite 仅用于 CV 本地开发、测试或离线缓冲。
2. **FastAPI 是 MySQL 唯一写入边界**。CV 不依赖 Agent ORM 或数据库连接。
3. CV 负责采集事实和事件生命周期；Agent/Web 负责查询、解释、编排、展示和报告。
4. Chroma 只存施工方案、规范和项目资料等非结构化知识；实时事件与摄像头状态不进入向量库。
5. Redis 仅作缓存、限流、任务状态、Pub/Sub 或分布式锁，不能作为事件事实来源。

## 2. 分层职责

| 层 | 负责 | 不负责 |
|---|---|---|
| CV / `perception` | 视频接入、检测、危险区几何、`track_id`、人-头-帽匹配、状态机、证据图、事件上报 | LLM 对话、MySQL 业务查询、用户权限、日报写作 |
| Agent | FastAPI、LangChain、LangGraph、工具注册、事件校验、MySQL、RAG、报告编排 | 逐帧视频推理、直接操控检测器内部状态 |
| Web | 摄像头状态、违规列表、证据展示、区域配置、报告展示 | 直连 CV 本地文件、直连 MySQL、加载模型 |

`track_id` 是单摄像头、单次监控会话中的临时编号，不是人员真实身份，也不得作为跨摄像头主键。

## 3. Agent 架构约定

```text
FastAPI
  ├── API 路由与鉴权
  ├── 工具注册中心
  └── LangGraph 单一主执行图
        ├── 意图与参数校验
        ├── CV/摄像头工具
        ├── MySQL 查询
        ├── Chroma RAG
        ├── 分析
        └── 报告生成
```

- LangGraph 使用显式状态对象；只记录结构化执行状态、工具输入输出摘要和审计日志，不保存或暴露模型隐式思维链。
- 工具以 Pydantic 输入/输出模型注册；禁止在图节点中拼接未校验 SQL 或传递 CV 内部对象。
- MySQL 存摄像头、围栏、违规事件、报告任务、用户与审计；Redis 和 Chroma 均不承担事务主存职责。

## 4. 违规事件契约（Event Contract v1）

同一事件从创建、升级到关闭，始终使用同一个 `event_uuid`；CV 可重复投递，Agent 必须幂等 upsert。

```json
{
  "schema_version": "1.0",
  "event_uuid": "a5d10bde-ef52-4ef7-8471-50b74c864623",
  "event_action": "UPSERT",
  "camera_id": "cam_crane_01",
  "monitor_session_id": "run_20260925_001",
  "track_id": 12,
  "violation_type": "DANGER_ZONE_INTRUSION",
  "severity": "WARNING",
  "status": "ACTIVE",
  "zone_id": "zone_crane_operational",
  "zone_name": "吊装禁行区",
  "occurred_at_utc": "2026-09-25T10:30:00Z",
  "resolved_at_utc": null,
  "duration_seconds": 0.0,
  "snapshot_uri": "snapshots/20260925/a5d10bde.jpg",
  "model_name": "helmet_head_person_m",
  "model_version": "legacy-yolov5",
  "extra_details": {
    "dwell_threshold_seconds": 5.0,
    "bbox": [120.0, 90.0, 280.0, 500.0],
    "feet_point": [200.0, 500.0]
  }
}
```

| 字段 | 约束 |
|---|---|
| `event_uuid` | UUID，MySQL 唯一索引；重复提交只更新同一记录 |
| `camera_id` | 由 Agent/MySQL 创建并下发；不可用流地址替代 |
| `monitor_session_id` | 每次启动监控时生成；与 `track_id` 共同限定目标语义 |
| `violation_type` | `NO_HELMET`、`DANGER_ZONE_INTRUSION`、`DWELL_TIMEOUT` |
| `severity` | `INFO`、`WARNING`、`CRITICAL` |
| `status` | `ACTIVE`、`RESOLVED`、`FALSE_ALARM` |
| `occurred_at_utc` | ISO 8601 UTC 时间，用于 MySQL、Web 日期查询与日报 |
| `duration_seconds` | CV 用单调时钟或视频时间戳计算后传递 |
| `snapshot_uri` | 相对媒体 key 或对象存储 key；禁止传 CV 主机绝对路径 |

CV 当前的单调时间适合计算时长，但不适合数据库审计：

```text
内部计时：monotonic / frame_timestamp → duration_seconds
业务审计：UTC wall-clock → occurred_at_utc / resolved_at_utc
```

## 5. 摄像头与危险区域配置契约

MySQL 是摄像头和围栏配置的唯一事实来源。CV 可以缓存，但必须按 `config_version` 刷新。

```json
{
  "camera_id": "cam_crane_01",
  "config_version": 3,
  "source_resolution": {"width": 1920, "height": 1080},
  "zones": [
    {
      "zone_id": "zone_crane_operational",
      "zone_name": "吊装禁行区",
      "polygon": [[402, 234], [497, 182], [727, 432], [364, 456]],
      "enabled": true,
      "alarm_dwell_threshold_seconds": 5.0
    }
  ]
}
```

- 顶点采用原始视频帧像素坐标，不是浏览器或 Qt 控件坐标。
- 围栏至少有 3 点，按边界顺序排列，无需重复首点。
- `zone_id` 稳定不变，`zone_name` 是可修改的显示名。
- Web 更新后，FastAPI 校验顶点、边界、分辨率并持久化；CV 不重复实现配置管理。
- CV 按脚底接地点判定入侵，策略与停留阈值由配置下发。

## 6. 最小内部 API

| 方法 | 路径 | 调用方 | 用途 |
|---|---|---|---|
| `POST` | `/internal/v1/perception/events` | CV → Agent | 幂等创建或更新违规事件 |
| `PUT` | `/internal/v1/perception/cameras/{camera_id}/status` | CV → Agent | 上报在线、FPS、人数和模型信息 |
| `GET` | `/internal/v1/perception/cameras/{camera_id}/config` | CV → Agent | 获取围栏和运行配置 |
| `PUT` | `/internal/v1/cv-nodes/{node_id}/heartbeat` | CV → Agent | 节点专属令牌心跳、活动会话数与容量 |
| `POST` | `/control/v1/sessions` | Agent → CV | 节点专属令牌启动会话，返回会话 ID |
| `DELETE` | `/control/v1/sessions/{camera_id}` | Agent → CV | 停止会话 |
| `GET` | `/control/v1/sessions/{camera_id}/preview.mjpeg` | Agent → CV | 读取节点 MJPEG，供 Agent 代理 |
| `GET` | `/control/v1/media-files` | Agent → CV | 仅浏览 `CV_ALLOWED_MEDIA_ROOTS` 内的视频文件 |
| `GET` | `/api/v1/cv-nodes/{node_id}/media-files` | Web → Agent → CV | 管理员通过 Agent 代理浏览节点本地视频文件 |
| `PUT` | `/api/v1/managed-cameras/{camera_id}/source` | Web → Agent | 修改停止状态摄像头的显示名、节点或视频源 |
| `POST` | `/api/v1/cameras/{camera_id}/monitoring:start` | Web → Agent → CV | 异步启动，返回监控会话 ID |
| `POST` | `/api/v1/cameras/{camera_id}/monitoring:stop` | Web → Agent → CV | 停止监控 |
| `GET` | `/api/v1/violations` | Web/Agent | 分页查询违规事件 |
| `GET` | `/api/v1/violations/statistics` | Agent | 查询报告统计 |
| `PUT` | `/api/v1/cameras/{camera_id}/zones` | Web/Agent | 校验并更新围栏，产生新配置版本 |

启动视频监控必须是异步任务。请求响应只返回 `monitor_session_id` 与状态，不能在 HTTP 请求线程中持续进行视频推理。

CV Control 服务通过 `python3 -m uvicorn perception.control_api:create_control_app --factory --port 8100` 运行。它只接受 Agent 的节点专属 Bearer Token；本地文件源须位于 `CV_ALLOWED_MEDIA_ROOTS`，浏览器只访问 Agent 的预览代理。Web 的“选择文件”弹窗展示的是所选 **CV 节点** 的允许目录，而不是操作员浏览器所在电脑的文件系统；选择结果由 Agent 加密保存为节点本地路径。

## 7. 存储与媒体规则

| 存储 | 生产用途 | 禁止用途 |
|---|---|---|
| MySQL | 事件、摄像头、围栏、会话、报告、审计 | 视频/截图二进制、隐式思维链 |
| SQLite | 单机测试、开发、离线 CV outbox | 与 MySQL 双写并同时做主库 |
| Redis | 缓存、任务状态、限流、短期 Pub/Sub、锁 | 唯一事件存档 |
| Chroma | 规范、方案和项目资料 RAG | 实时事件/状态查询 |
| 媒体存储 | 截图、短视频证据，返回 URI | 暴露仅本机可见的绝对路径 |

如需离线能力，CV 使用 SQLite outbox 暂存未投递事件，网络恢复后依据 `event_uuid` 重试；第一期不实现 outbox 时必须记录并显式报告失败，不能静默丢弃 `CRITICAL` 事件。

## 8. 工具注册与 LangGraph 状态

第一期工具：

```text
start_camera_monitoring(camera_id) -> MonitoringSession
stop_camera_monitoring(camera_id) -> MonitoringSession
get_camera_status(camera_id) -> CameraStatus
query_violations(camera_id, start_time, end_time, filters) -> ViolationReport
configure_danger_zone(camera_id, zone) -> DangerZoneConfig
generate_daily_safety_report(date, camera_ids) -> ReportPayload
```

LangGraph 状态只保存已校验参数、查询结果引用、报告草稿和错误信息。敏感流地址和未校验 CV 原始对象不得进入 LLM 上下文。

## 9. 联调门禁

1. 固定 `sample_walk.mp4` 可产生“进入 → 升级/停留 → 离开”完整事件链。
2. 同一 `event_uuid` 重复提交三次后，MySQL 仅一条记录且状态正确更新。
3. Web 可按摄像头、时间、严重级别查询事件并打开 `snapshot_uri`。
4. Web 更新围栏后，CV 获取最新 `config_version` 并按原始帧坐标判定。
5. CV 不可用时，Agent 返回明确状态，不能把缓存伪装成实时结果。
6. RAG 只能引用 Chroma 资料，不得修改 MySQL 中的事件事实。

## 10. 待确认项与实施顺序

| 项目 | 建议决定 | 责任方 | 状态 |
|---|---|---|---|
| 事件写入 | CV 调用 FastAPI；FastAPI 写 MySQL | Agent + CV | 待确认 |
| 媒体存储 | 比赛期共享媒体目录并由 FastAPI 暴露 URL；后续对象存储 | Web + CV | 待确认 |
| 服务鉴权 | 内部 Bearer Token；生产期服务身份/密钥轮换 | Agent | 待确认 |
| 离线缓冲 | SQLite outbox 或显式失败日志 | CV | 待确认 |
| 围栏格式 | 本文 `camera_id + config_version + zones` | Agent + Web + CV | 待确认 |
| 状态推送 | 第一阶段轮询；第二阶段 Redis Pub/Sub + WebSocket | Agent + Web | 待确认 |

实施顺序：

1. Agent 建立 Pydantic 契约、MySQL migration 和事件 upsert API。
2. CV 为现有 `ViolationEvent` 实现 Event Contract v1 转换器。
3. Web 使用固定事件 fixture 开发事件列表、详情和截图展示。
4. CV 与 Agent 完成固定视频端到端联调。
5. Web 接入真实 API 和围栏读取/更新。
6. 后续接入 Redis 协调与 Chroma RAG。
