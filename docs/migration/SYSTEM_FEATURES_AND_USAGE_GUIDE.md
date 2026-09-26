# 智能建造工程智能体 (Civil Engineering Agent) 系统功能与使用指南

> **文档版本**：v1.2
> **更新时间**：2026-09-25  
> **归档路径**：`docs/migration/SYSTEM_FEATURES_AND_USAGE_GUIDE.md`  
> **适用受众**：算法工程师、后端工程师、前端开发者、系统运维与现场实施人员。

---

> 本文以当前仓库实现和自动化测试为准。Web 仪表盘、对象存储服务及生产部署编排不在本仓库内；文中示例须按实际部署的数据库、令牌与媒体存储配置调整。

## 目录

- [1. 系统架构与分层定位](#1-系统架构与分层定位)
- [2. 视觉安全感知子系统 (Perception) 功能详解](#2-视觉安全感知子系统-perception-功能详解)
  - [2.1 目标检测与多模型适配](#21-目标检测与多模型适配)
  - [2.2 多相机隔离的目标追踪 (ByteTrack)](#22-多相机隔离的目标追踪-bytetrack)
  - [2.3 人-头-帽空间拓扑匹配](#23-人-头-帽空间拓扑匹配)
  - [2.4 电子围栏判定与双向坐标变换](#24-电子围栏判定与双向坐标变换)
  - [2.5 单调时钟防抖状态机与滞留告警](#25-单调时钟防抖状态机与滞留告警)
  - [2.6 本地持久化与快照渲染 (EventStore)](#26-本地持久化与快照渲染-eventstore)
  - [2.7 离线缓冲发布器 (OutboxStore & Publisher)](#27-离线缓冲发布器-outboxstore--publisher)
  - [2.8 无头会话调度器与心跳守护 (SessionRunner)](#28-无头会话调度器与心跳守护-sessionrunner)
- [3. 智能体中枢子系统 (Agent) 功能详解](#3-智能体中枢子系统-agent-功能详解)
  - [3.1 FastAPI 契约层与 MySQL 事务持久化](#31-fastapi-契约层与-mysql-事务持久化)
  - [3.2 围栏与摄像头在线配置管理](#32-围栏与摄像头在线配置管理)
  - [3.3 LangGraph 对话图与事实驱动原则](#33-langgraph-对话图与事实驱动原则)
  - [3.4 LLM 适配器与多模型热切换 (DeepSeek)](#34-llm-适配器与多模型热切换-deepseek)
- [4. 快速上手与操作指南](#4-快速上手与操作指南)
  - [4.1 环境准备与依赖安装](#41-环境准备与依赖安装)
  - [4.2 感知子系统 CLI 命令行运行](#42-感知子系统-cli-命令行运行)
  - [4.3 感知子系统 GUI 桌面客户端运行](#43-感知子系统-gui-桌面客户端运行)
  - [4.4 启动 Agent 智能体后台服务](#44-启动-agent-智能体后台服务)
  - [4.5 CV 与 Agent 端到端全链路实操演练](#45-cv-与-agent-端到端全链路实操演练)
- [5. 关键 API 接口与命令行参数参考](#5-关键-api-接口与命令行参数参考)
  - [5.1 CLI 参数参考](#51-cli-参数参考)
  - [5.2 核心 REST API 清单](#52-核心-rest-api-清单)
- [6. 自动化测试体系与质量验收](#6-自动化测试体系与质量验收)

---

## 1. 系统架构与分层定位

当前代码实现的是感知层和 Agent 服务的最小闭环：感知端处理视频、持久化本地事件并通过 HTTP 投递；Agent 端验证契约、写入关系数据库，并提供查询、统计、配置和问答 API。

```mermaid
flowchart TD
    subgraph S1["感知层 (Perception / CV)"]
        Stream["现场视频流 (RTSP / 文件 / 摄像头)"] --> Runner["无头调度器 (CameraSessionRunner)"]
        Runner --> Det["目标检测 (YOLOv5 / v8)"]
        Det --> Track["目标追踪 (ByteTrack)"]
        Track --> Topo["拓扑匹配 (人-头-帽)"]
        Topo --> Geo["空间几何 (电子围栏)"]
        Geo --> FSM["防抖状态机 (进入/滞留/离开)"]
        FSM --> EvStore["本地 SQLite & 快照渲染"]
        FSM --> Outbox["离线缓冲 (SQLite Outbox)"]
    end

    subgraph S2["智能体中枢层 (Agent / FastAPI)"]
        Outbox --"HTTP POST (幂等 UPSERT)"--> APIGW["FastAPI 接入网关"]
        Runner --"HTTP PUT (心跳 / FPS / 合规率)"--> APIGW
        APIGW --> DB[("MySQL 业务主库")]
        APIGW --> Graph["LangGraph 认知图编排"]
        Graph --> LLM["大模型推理 (DeepSeek / OpenAI)"]
        Graph --> Tools["工具调用 (SQL事实查询 / 统计聚合)"]
    end

    subgraph S3["当前仓库提供的交互入口"]
        Docs["FastAPI /docs"]
        CLI["感知运维 CLI (perception.cli)"]
        GUI["本地桌面批处理客户端"]
    end

    APIGW --> Docs
    Runner -.-> CLI
    Det -.-> GUI
```

### 核心设计原则
1. **写边界隔离**：感知端不直接连接 Agent 数据库；事件和状态经 FastAPI 内部接口投递，且接口要求 Bearer 令牌。
2. **媒体引用约束**：服务端仅接受相对 `snapshot_uri`（例如 `snapshots/20260925/{event_uuid}.jpg`），拒绝绝对路径和包含 `..` 的路径。
3. **事件幂等**：同一 `event_uuid` 可从活动状态更新为已解决状态；`RESOLVED` 必须提供不早于发生时间的 `resolved_at_utc`。
4. **问答边界**：问答图只能调用违规查询、统计、单摄状态、全部摄像头状态和当前天气工具；“所有/全部摄像头”的状态、在线或帧率问法固定路由到全部状态工具，不由模型猜测摄像头 ID。默认使用 DeepSeek，必须配置 `AGENT_LLM_API_KEY`；离线开发和测试可显式设置 `AGENT_LLM_PROVIDER=fake`。天气工具固定访问 Open-Meteo，模型仅能提供受长度限制的地点名称。

---

## 2. 视觉安全感知子系统 (Perception) 功能详解

感知层代码位于 `perception/` 目录下，具备从像素解码到事件上报的完整闭环能力。

### 2.1 目标检测与多模型适配
- **统一抽象基类 [`BaseDetector`](../../perception/detectors/base.py)**：定义统一的 `load_model()` 与 `detect()` 接口，业务层面向接口编程；
- **旧版 YOLO 适配器 [`LegacyYOLOv5Adapter`](../../perception/detectors/legacy_yolo_adapter.py)**：加载 `helmet_head_person_s.pt` 三分类（`person`、`head`、`helmet`）权重；
- **现代 YOLO 适配器 [`UltralyticsDetector`](../../perception/detectors/ultralytics_detector.py)**：基于 Ultralytics 引擎加载兼容权重；实际支持范围取决于已安装的 Ultralytics 版本和权重格式；
- **设备自动仲裁 (`get_optimal_device`)**：支持命令行显式指定、`PERCEPTION_DEVICE` 环境变量、CUDA 自动检测与 CPU 自动回落。

### 2.2 多相机隔离的目标追踪 (ByteTrack)
- **纯 Python 实现**：位于 [`perception/tracking/byte_tracker.py`](../../perception/tracking/byte_tracker.py)，不依赖本项目额外的 C++ 或 Cython 扩展；
- **实例级 ID 隔离**：彻底重构旧版全局静态自增 ID，每个摄像头实例持有独立的 `_next_id` 计数器，杜绝多机位并发监控时的 Track ID 碰撞。

### 2.3 人-头-帽空间拓扑匹配
- **解剖学上部几何裁剪**：人体头部与安全帽天然位于人体边界框（Bounding Box）上方约前 35% 区域；
- **二分图匹配算法**：在 [`perception/geometry/topology.py`](../../perception/geometry/topology.py) 中，当单帧出现多个工人与安全帽时，按 IoU 代价矩阵进行匹配，以降低错配概率；
- **类别语义解耦**：支持 `worker`、`person`、`hardhat`、`safety_cap` 等多种标签语义别名，适应不同模型训练数据集。

### 2.4 电子围栏判定与双向坐标变换
- **脚底触地几何点（Feet Ground Point）**：取人员边界框底边中点 $(x_{\text{mid}}, y_2)$ 作为判定基准；与传统用中心点判定相比，彻底解决了施工人员身体切入边缘时的漏报问题；
- **任意多边形包含判断**：基于 OpenCV 射线交叉法与点到多边形测试算法；
- **GUI 双向坐标等比例映射**：在播放器视口存在黑边（Letterbox）时，严格计算 Padding 与 Scale，确保 UI 鼠标绘制坐标与视频原始分辨率之间取整误差 $\le 1$ 像素。

### 2.5 单调时钟防抖状态机与滞留告警
- **时间基准**：运行中的实时流和本地文件回放均将 `time.monotonic()` 传给防抖状态机；它与会话的 `TimeAnchor` 使用同一时钟域，确保 `occurred_at_utc`、`resolved_at_utc` 是当前审计时间。视频 FPS/PTS 仅用于播放节流与媒体定位，绝不能直接作为 `TimeAnchor` 的输入；
- **防抖去重生命周期（[`WorkerSafetyMonitor`](../../perception/tracking/state_machine.py)）**：
  - **进入确认**：目标连续在区域内驻留超过 $T_{\text{enter}}$ 帧，触发入界警示（`WARNING`）；
  - **滞留超时升级**：驻留总时长累计达到预设阈值（默认 5.0 秒），无缝升级为严重告警（`CRITICAL`），沿用原 `event_uuid` 并标记升级原因；
  - **离开冷却结案**：目标连续消失超过 $T_{\text{exit}}$ 帧，触发结案（`RESOLVED`），准确结算持续秒数；
  - **未戴安全帽防抖**：目标连续未戴安全帽超过 $T_{\text{helmet}}$ 帧才触发违规，避免偶尔低头遮挡产生的瞬态误报。

### 2.6 本地持久化与快照渲染 (EventStore)
- **SQLite 事件存储**：在 [`perception/storage/event_store.py`](../../perception/storage/event_store.py) 中自动维护本地 `violation_events` 表；
- **可视化违规快照生成**：事件持久化时可在原图上叠加区域、目标框和事件文字，并保存 JPEG 快照；具体标注内容随事件类型和可用图像数据而定；
- **标准路径契约**：统一存储至 `snapshots/YYYYMMDD/{event_uuid}.jpg`。

### 2.7 离线缓冲发布器 (OutboxStore & Publisher)
- **专用 Outbox 队列**：基于独立 SQLite 库，将待发事件加入 `outbox_events` 表；
- **网络容灾与指数退避**：当网络中断或 Agent 返回 5xx 时，按 $2^{\text{retry}}$ 执行退避重试；网络恢复后通过 `flush_outbox()` 自动补发；
- **致命错误熔断**：遇到 400/422 客户端格式错误时，自动标记为不可恢复终态并记录日志，避免无效死循环请求。

### 2.8 无头会话调度器与心跳守护 (SessionRunner)
- **会话服务 [`CivilSafetyPerceptionService`](../../perception/services/session_runner.py)**：提供会话管理与本地日报统计能力；
- **独立线程运行 [`CameraSessionRunner`](../../perception/services/session_runner.py)**：管理单路解码、推理、防抖状态与时间锚点；多相机场景由调用方创建并管理多个运行器；
- **周期性心跳**：默认每 5 秒上报 FPS、已处理帧号、在线工人数及安全帽合规率；间隔可通过 CLI 参数调整；
- **配置在线轮询与优雅降级**：定时拉取最新围栏配置；配置端点不可用时，回退到 CLI 传入的区域或本地默认配置。

---

## 3. 智能体中枢子系统 (Agent) 功能详解

Agent 层代码位于 `agent/` 目录下，负责事件接收校验、关系数据库持久化、查询统计及受限工具驱动的 LLM 对话。

### 3.1 FastAPI 契约层与关系数据库持久化
- **API 路由规范**：
  - `/internal/v1/perception/events`：供 CV 调用的违规事件上报接口（基于 `event_uuid` 实现严格幂等的 UPSERT）；
  - `/internal/v1/perception/cameras/{camera_id}/status`：供 CV 调用的相机状态与心跳上报接口；
  - `/internal/v1/perception/cameras/{camera_id}/config`：供 CV 调用的围栏参数下发接口；
  - `/api/v1/violations`：供调用方查询安全违规列表；
  - `/api/v1/agent/chat`：面向大模型的人机对话接口；
  - `/api/v1/agent/safety-query`：结构化安全查询接口。
- **关系数据库**：通过 SQLAlchemy 持久化违规、相机状态和相机配置。运行时数据库由 `AGENT_DATABASE_URL` 指定；测试使用 SQLite，生产 MySQL 迁移脚本位于 `agent/db/migrations/`。当前迁移不包含日报任务表。

### 3.2 围栏与摄像头在线配置管理
- 支持在 Agent 侧对每个摄像头配置专属的危险区域多边形、源分辨率、滞留阈值和防抖帧数；
- 配置带有单调自增的 `config_version`，CV 会话轮询到新版本即可实现**线上热更新**。

### 3.3 LangGraph 对话图与事实驱动原则
- **结构化图状态**：在 `agent/graph/chat_graph.py` 中编排模型决策、受限工具调用和回复生成；工具调用次数受 `AGENT_TOOL_MAX_CALLS`（1–2）限制；
- **证据接地**：对话响应可附带查询到的 `event_uuid`、发生时间和 `snapshot_uri`。媒体文件的实际托管与前端渲染由调用方部署负责。
- **当前天气查询**：当问题包含地点与天气、气温、降雨或风速时，Agent 可调用 `get_current_weather`。该工具先通过 Open-Meteo 地理编码解析地点，再获取当前实况；失败时按聊天接口既有降级语义返回，不会编造结果。

### 3.4 LLM 适配器与可配置模型选择 (DeepSeek)
- **协议端口 [`ChatModelPort`](../../agent/llm/protocol.py)**：定义统一的聊天接口契约；
- **DeepSeek 适配 [`DeepSeekChatModel`](../../agent/llm/deepseek_adapter.py)**：通过可配置的兼容接口访问 DeepSeek 模型；
- **离线测试桩 [`FakeChatModel`](../../agent/llm/fake_adapter.py)**：支持无网络、无 API Key 的本地测试。

### 3.5 Phase 2：远程 CV 节点调度与视频预览
- **节点管理**：Agent 维护多个 CV Control 节点的在线心跳、容量和专属控制令牌；摄像头由管理员手动分配节点。
- **源配置安全**：支持 RTSP 与 CV 节点本地文件；完整源地址使用 `AGENT_CREDENTIAL_ENCRYPTION_KEY` 加密存储，Web 只可见脱敏地址。
- **会话与预览**：Agent 通过 HTTP 启停 CV 会话；CV 输出最新帧 MJPEG，Web 通过 Agent 的 `/api/v1/cameras/{camera_id}/preview` 预览，绝不直连 CV。
- **配置编辑与文件选择**：已绑定摄像头可编辑。若会话正在运行，Web 会先提示并停止会话；“选择文件”弹窗浏览的是目标 CV 节点的 `CV_ALLOWED_MEDIA_ROOTS`，并非浏览器电脑的任意文件系统。
- **证据截图共享目录**：CV 必须将 `CV_SNAPSHOT_DIR` 配置为与 Agent 的 `AGENT_MEDIA_ROOT/snapshots` 相同的共享/挂载路径。`snapshot_uri` 为 `snapshots/YYYYMMDD/*.jpg`，由 Agent 的 `/media/` 静态挂载对 Web 提供服务；本机启动脚本会自动统一为 `runs/media/snapshots`。
- **视频辅助标定**：危险区域标定页默认叠加 Agent 代理的实时 MJPEG，可暂停为最新 JPEG 帧后拖拽或点击顶点；预览不可用时自动回退网格。支持一个摄像头配置多个围栏，所有顶点均按 `source_resolution` 保存为原始帧像素坐标。

---

## 4. 快速上手与操作指南

### 4.1 环境准备与依赖安装

推荐 Python 3.10+。感知层和 Agent 层的依赖清单分开维护；桌面客户端还需要本机可用的图形环境。

```bash
# 1. 克隆进入工程目录
cd /home/jjc/projects/python/civil_engineering_agent

# 2. 安装感知层与智能体运行依赖
pip install -r requirements.txt
pip install -r requirements-agent.txt
```

启动 Agent 前，必须配置以下环境变量（也可写入项目根目录 `.env`）：

```bash
export AGENT_DATABASE_URL='sqlite+pysqlite:///./data/agent.db'
export AGENT_AUTO_CREATE_SCHEMA=true       # 仅适合本地验证
export INTERNAL_PERCEPTION_TOKEN='replace-with-a-secret'
export AGENT_LLM_PROVIDER=deepseek          # 默认值；必须同时配置 AGENT_LLM_API_KEY
export AGENT_LLM_API_KEY='your-deepseek-api-key'
export AGENT_ADMIN_TOKEN='admin-secret-for-camera-management'
export AGENT_CREDENTIAL_ENCRYPTION_KEY='a-valid-fernet-key'
```

可使用以下命令生成一次 Fernet 加密密钥：

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

生产环境应通过 Alembic 执行 `agent/db/migrations/` 中的迁移，不应依赖 `AGENT_AUTO_CREATE_SCHEMA=true`。

#### 命令：启动 CV Control 节点（Phase 2）

先由管理员调用 `POST /api/v1/cv-nodes` 创建节点并安全保存一次性返回的 `control_token`，然后在 CV 主机配置：

```bash
export CV_NODE_ID='cv-east-01'
export CV_NODE_TOKEN='node-control-token'
export AGENT_URL='http://agent-host:8000'
export CV_ALLOWED_MEDIA_ROOTS='/srv/cv-media'
export INTERNAL_PERCEPTION_TOKEN='same-internal-token'
python3 -m uvicorn perception.control_api:create_control_app --factory --host 0.0.0.0 --port 8100
```

节点每 5 秒向 Agent 心跳。Web 使用 `VITE_AGENT_ADMIN_TOKEN` 访问摄像头与节点管理页；MJPEG 预览不向浏览器暴露该令牌或节点地址。

#### 本机一键 Phase 2 启动

项目根目录 `.env` 配置 `CV_NODE_ID`、`CV_NODE_TOKEN`、`CV_CONTROL_PORT`、`CV_NODE_CAPACITY` 和 `CV_ALLOWED_MEDIA_ROOTS` 后，统一脚本会自动登记本机节点、启动 CV Control、等待心跳上线，并以默认样例视频创建和启动 `cam_field_01`：

```bash
./scripts/start_stack.sh
```

脚本只管理它自身启动的进程；若 8000 已有 Agent 服务，它会安全退出，必须先停止旧脚本实例再重新启动。

#### 本地文件事件时间与排查

本地 MP4 等文件源会循环播放以便演示，但每次检测到的违规仍按**实际监控运行时间**写入 MySQL，而不是按素材从第 0 秒开始的相对时间写入。违规事件中心按 `occurred_at_utc` 倒序显示，因此新事件应出现在列表顶部。

若新事件没有出现在顶部，先确认以下两项：

1. CV Control 日志中 `POST /internal/v1/perception/events` 返回 `200 OK`；
2. 在违规事件中心刷新列表，确认 `monitor_session_id` 属于当前启动的会话，且 `occurred_at_utc` 为当天时间。

旧版本曾将文件视频的“帧序号 / FPS”错误传入以单调时钟建立的 `TimeAnchor`，会导致记录被回填到历史日期；该历史数据保留原值，新版本只保证修复后生成的事件使用正确时间。

---

### 4.2 感知子系统 CLI 命令行运行

无需启动窗口，即可运行视频流监控或从本地 SQLite 事件库生成日报统计。`run` 子命令目前使用旧版 YOLOv5 适配器，因此指定的权重必须存在且与该适配器兼容。

#### 命令 1：启动监控流 (`run`)

```bash
# 场景 A：使用离线视频样例测试
python3 -m perception.cli run \
  --camera-id cam_gate_01 \
  --source tests/fixtures/sample_walk.mp4 \
  --agent-url http://127.0.0.1:8000 \
  --device auto

# 场景 B：接入施工现场 RTSP 高清监控流
python3 -m perception.cli run \
  --camera-id cam_tower_crane \
  --source "rtsp://user:password@camera.example:554/live" \
  --agent-url http://127.0.0.1:8000 \
  --device cuda:0 \
  --heartbeat-interval 5.0
```

> **操作提示**：内部投递需要令牌，因此运行前应设置与 Agent 相同的 `INTERNAL_PERCEPTION_TOKEN`。按下 `Ctrl + C` 会请求停止会话；运行器会尝试上报离线状态并刷新到期的 Outbox 项。

#### 命令 2：生成安全巡检日报数据 (`report`)

```bash
python3 -m perception.cli report --date 2026-09-25 --event-db data/events.db
```

终端将打印结构化的 JSON 统计数据（包含当日总违规数、各机位分布、违规类型占比与证据图 URI）。

---

### 4.3 感知子系统 GUI 桌面客户端运行

在有图形界面的开发机上，支持鼠标实时交互与绘制电子围栏。

```bash
python3 -m perception.gui.app
```

- 客户端用于选择本地图片或视频、执行批处理推理、预览结果及打开结果目录；并非多相机监控控制台。
- 它优先使用 `PERCEPTION_MODEL_WEIGHTS` 指向的现有权重；否则依次尝试仓库内的默认权重。均不可用时会使用 `MockDetector`，只适合演示和测试，不代表真实检测结果。
- 默认危险区来自 [`perception/configs/default_danger_zones.json`](../../perception/configs/default_danger_zones.json)。

---

### 4.4 启动 Agent 智能体后台服务

```bash
# 启动 FastAPI 服务工厂（开发模式；需先配置第 4.1 节环境变量）
python3 -m uvicorn agent.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

服务启动后，可在浏览器访问 `http://127.0.0.1:8000/docs` 查看交互式 Swagger API 文档。

---

### 4.5 CV 与 Agent 端到端全链路实操演练

完成以下步骤可验证当前仓库的感知—Agent 最小闭环：

```bash
# 步骤 1：后台启动 Agent API 服务工厂
python3 -m uvicorn agent.main:create_app --factory --port 8000 &

# 步骤 2：启动 CV 监控会话，灌入测试视频
python3 -m perception.cli run \
  --camera-id cam_field_01 \
  --source tests/fixtures/sample_walk.mp4 \
  --agent-url http://127.0.0.1:8000

# 步骤 3：查询 Agent 端已入库事件、统计与相机状态
curl -X GET "http://127.0.0.1:8000/api/v1/violations?camera_id=cam_field_01"
curl -X GET "http://127.0.0.1:8000/api/v1/cameras/cam_field_01/status"
```

若 Agent 暂不可达，请检查 `data/outbox.db` 中的待投递记录、令牌一致性及服务日志。

---

## 5. 关键 API 接口与命令行参数参考

### 5.1 CLI 参数参考 (`perception.cli`)

| 子命令 | 参数 | 类型 | 默认值 | 作用描述 |
| :--- | :--- | :--- | :--- | :--- |
| `run` | `--camera-id` | string | **必填** | 摄像头唯一业务编号 (如 `cam_crane_01`) |
| `run` | `--source` | string | **必填** | RTSP URL、本地 MP4/AVI 路径或 USB 摄像头编号 (`0`) |
| `run` | `--agent-url` | string | `http://127.0.0.1:8000` | Agent FastAPI 后端基地址 |
| `run` | `--weights` | string | `perception/weights/...` | 模型权重文件路径 |
| `run` | `--device` | string | `auto` | 计算设备：`auto` (优先GPU), `cpu`, `cuda:0` |
| `run` | `--zones-config` | string | `None` | 自定义危险区域 JSON 配置文件路径 |
| `run` | `--heartbeat-interval`| float | `5.0` | 状态心跳上报间隔时间 (秒) |
| `run` | `--outbox-db` | string | `data/outbox.db` | 离线事件暂存缓冲库路径 |
| `run` | `--event-db` | string | `data/events.db` | 本地归档事件数据库路径 |
| `run` | `--snapshot-dir` | string | `data/snapshots` | 本地快照根目录 |
| `run` | `--config-poll-interval` | float | `30.0` | 远程配置轮询间隔（秒） |
| `run` | `--model-name` / `--model-version` | string | `helmet_head_person_s` / `legacy-yolov5` | 上报的模型标识 |
| `report` | `--date` | string | **必填** | 查询日期，支持 `YYYYMMDD` 或 `YYYY-MM-DD` |
| `report` | `--event-db` | string | `data/events.db` | 本地归档事件数据库路径 |

---

### 5.2 核心 REST API 清单

#### 1. 内部感知事件上报 (Internal Perception Events)
- **请求方法**：`POST /internal/v1/perception/events`
- **鉴权**：`Authorization: Bearer <INTERNAL_PERCEPTION_TOKEN>`；其余内部感知接口也需要该请求头。
- **请求体规格**：
  ```json
  {
    "schema_version": "1.0",
    "event_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "event_action": "UPSERT",
    "camera_id": "cam_crane_01",
    "monitor_session_id": "session_cam_crane_01_20260925",
    "track_id": 42,
    "violation_type": "DANGER_ZONE_INTRUSION",
    "severity": "CRITICAL",
    "status": "ACTIVE",
    "zone_name": "吊装禁行区",
    "occurred_at_utc": "2026-09-25T10:30:00Z",
    "duration_seconds": 5.2,
    "snapshot_uri": "snapshots/20260925/3fa85f64.jpg"
  }
  ```

#### 2. 相机运行心跳上报 (Camera Status Heartbeat)
- **请求方法**：`PUT /internal/v1/perception/cameras/{camera_id}/status`
- **请求体规格**：
  ```json
  {
    "camera_id": "cam_crane_01",
    "monitor_session_id": "session_cam_crane_01_20260925",
    "is_online": true,
    "fps": 24.8,
    "processed_frame_id": 1205,
    "active_workers_count": 6,
    "reported_at_utc": "2026-09-25T10:30:00Z",
    "extra_details": {"helmet_compliance_rate": 0.8333}
  }
  ```

#### 3. 智能问答与安全分析 (Chat Agent API)
- **请求方法**：`POST /api/v1/agent/chat`
- **请求体规格**：
  ```json
  {
    "question": "今天塔吊区有哪些严重的违规行为？",
    "conversation_id": "user_session_101"
  }
  ```
- **返回结果**：包含回答、可用的事实证据（`event_uuid`、发生时间、快照 URI）、工具调用记录及降级标识。

---

## 6. 自动化测试体系与质量验收

系统提供分层自动化测试套件，用于检查已实现的核心契约与回归场景；测试不能替代现场模型评估或生产验收。

```text
tests/
├── agent/                         # Agent 契约、配置、问答与模型工厂测试
│   ├── test_camera_config_api.py  # 围栏配置下发与版本管理
│   ├── test_chat_closed_loop.py   # 智能问答全流程
│   ├── test_llm_factory.py        # 模型工厂与热切换
│   └── test_minimal_closed_loop.py # 最小闭环测试
└── perception/                    # 感知模块测试
    ├── test_cli.py                # 命令行工具解析与报告测试
    ├── test_data_tools.py         # VOC/YOLO 数据转换工具
    ├── test_detector_interface.py # 检测器适配器抽象
    ├── test_event_store.py        # 本地 SQLite 存储与快照验证
    ├── test_geometry.py           # 触地判定与坐标变换
    ├── test_integration_contract.py # 跨系统契约与 Outbox 验证
    ├── test_regression.py         # YOLO 双适配器回归推理
    ├── test_safety_pipeline.py    # 端到端感知流水线
    ├── test_schemas.py            # 感知数据模型与序列化
    ├── test_session_runner.py     # 无头会话生命周期与心跳轮询
    ├── test_state_machine.py      # 防抖状态机与滞留升级
    ├── test_topology.py           # 人头帽解剖拓扑匹配
    ├── test_tracker.py            # ByteTrack 跨帧与多实例隔离
    └── test_video_pipeline.py     # 真实视频真值一致性
```

### 执行全量测试命令
```bash
python3 -m pytest tests/ -v
```
> **当前清单**：`tests/` 目录中有 52 个测试函数。请以本地执行命令的实际结果为准；本文件不对特定环境下的通过率作保证。
