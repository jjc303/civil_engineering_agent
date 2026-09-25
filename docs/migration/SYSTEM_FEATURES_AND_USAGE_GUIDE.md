# 智能建造工程智能体 (Civil Engineering Agent) 系统功能与使用指南

> **文档版本**：v1.0  
> **更新时间**：2026-09-25  
> **归档路径**：`docs/migration/SYSTEM_FEATURES_AND_USAGE_GUIDE.md`  
> **适用受众**：算法工程师、后厨/后端工程师、前端开发者、系统运维与现场实施人员。

---

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

本项目致力于构建面向建筑施工现场的**高可靠、端到端闭环安全生产智能体**，整体采用三层解耦架构：

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

    subgraph S3["交互层 (Web / Terminal)"]
        Web["Web 仪表盘 / 视频证据墙"]
        Chat["智能体人机交互对话终端"]
        CLI["感知运维 CLI (perception.cli)"]
    end

    APIGW --> Web
    Graph --> Chat
    Runner -.-> CLI
```

### 核心设计原则
1. **事实来源原则 (Source of Truth)**：违规事件由 CV 采集并由 Agent 写入 MySQL；大模型（LLM）**只能解释和汇总已入库的事实**，严禁模型凭空捏造事件、违规人数或现场时间。
2. **写边界隔离**：FastAPI 是进入 MySQL 生产数据库的唯一写入通道，CV 不直连 MySQL，亦不依赖 Agent ORM 模型。
3. **媒体引用解耦**：数据库仅保存标准相对媒体 URI（如 `snapshots/20260925/{event_uuid}.jpg`），底层物理图片存放在共享媒体卷或对象存储上，禁止向外泄露宿主机绝对路径。
4. **生命周期不变量**：一次违规事件从进入告警（`WARNING`）、滞留超时升级（`CRITICAL`）到离开结案（`RESOLVED`），**全程保持唯一的 `event_uuid`**。

---

## 2. 视觉安全感知子系统 (Perception) 功能详解

感知层代码位于 `perception/` 目录下，具备从像素解码到事件上报的完整闭环能力。

### 2.1 目标检测与多模型适配
- **统一抽象基类 [`BaseDetector`](file:///home/jjc/projects/python/civil_engineering_agent/perception/detectors/base.py)**：定义统一的 `load_model()` 与 `detect()` 接口，业务层完全面向接口编程；
- **旧版 YOLO 适配器 [`LegacyYOLOv5Adapter`](file:///home/jjc/projects/python/civil_engineering_agent/perception/detectors/legacy_yolo_adapter.py)**：平滑加载 `helmet_head_person_s.pt` 三分类（`person`, `head`, `helmet`）权重；
- **现代 YOLO 适配器 [`UltralyticsDetector`](file:///home/jjc/projects/python/civil_engineering_agent/perception/detectors/ultralytics_detector.py)**：基于官方 Ultralytics 引擎，支持 YOLOv8/v9/v11 权重的即插即用；
- **设备自动仲裁 (`get_optimal_device`)**：支持命令行显式指定、`PERCEPTION_DEVICE` 环境变量、CUDA 自动检测与 CPU 自动回落。

### 2.2 多相机隔离的目标追踪 (ByteTrack)
- **纯 Python 移植实现**：位于 [`perception/tracking/byte_tracker.py`](file:///home/jjc/projects/python/civil_engineering_agent/perception/tracking/byte_tracker.py)，完全摆脱对 C++ 扩展和 Cython 的编译依赖；
- **实例级 ID 隔离**：彻底重构旧版全局静态自增 ID，每个摄像头实例持有独立的 `_next_id` 计数器，杜绝多机位并发监控时的 Track ID 碰撞。

### 2.3 人-头-帽空间拓扑匹配
- **解剖学上部几何裁剪**：人体头部与安全帽天然位于人体边界框（Bounding Box）上方约前 35% 区域；
- **匈牙利二分图匹配算法**：在 [`perception/geometry/topology.py`](file:///home/jjc/projects/python/civil_engineering_agent/perception/geometry/topology.py) 中，当单帧视野出现多个工人、多顶安全帽时，使用全局最优 IoU 代价矩阵进行二分匹配，杜绝“张冠李戴”；
- **类别语义解耦**：支持 `worker`、`person`、`hardhat`、`safety_cap` 等多种标签语义别名，适应不同模型训练数据集。

### 2.4 电子围栏判定与双向坐标变换
- **脚底触地几何点（Feet Ground Point）**：取人员边界框底边中点 $(x_{\text{mid}}, y_2)$ 作为判定基准；与传统用中心点判定相比，彻底解决了施工人员身体切入边缘时的漏报问题；
- **任意多边形包含判断**：基于 OpenCV 射线交叉法与点到多边形测试算法；
- **GUI 双向坐标等比例映射**：在播放器视口存在黑边（Letterbox）时，严格计算 Padding 与 Scale，确保 UI 鼠标绘制坐标与视频原始分辨率之间取整误差 $\le 1$ 像素。

### 2.5 单调时钟防抖状态机与滞留告警
- **时间基准**：严格采用单调时钟 `time.monotonic()`（实时流）或 PTS 帧时间戳（离线文件），杜绝按固定帧数估算时间的传统缺陷；
- **防抖去重生命周期 ([`WorkerSafetyMonitor`](file:///home/jjc/projects/python/civil_engineering_agent/perception/tracking/state_machine.py))**：
  - **进入确认**：目标连续在区域内驻留超过 $T_{\text{enter}}$ 帧，触发入界警示（`WARNING`）；
  - **滞留超时升级**：驻留总时长累计达到预设阈值（默认 5.0 秒），无缝升级为严重告警（`CRITICAL`），沿用原 `event_uuid` 并标记升级原因；
  - **离开冷却结案**：目标连续消失超过 $T_{\text{exit}}$ 帧，触发结案（`RESOLVED`），准确结算持续秒数；
  - **未戴安全帽防抖**：目标连续未戴安全帽超过 $T_{\text{helmet}}$ 帧才触发违规，避免偶尔低头遮挡产生的瞬态误报。

### 2.6 本地持久化与快照渲染 (EventStore)
- **SQLite 事件存储**：在 [`perception/storage/event_store.py`](file:///home/jjc/projects/python/civil_engineering_agent/perception/storage/event_store.py) 中自动维护本地 `violation_events` 表；
- **可视化违规快照生成**：违规发生时，自动在原图上叠加红色半透明危险多边形遮罩、目标人员框，以及顶部包含 `[CRITICAL] NO_HELMET | Cam: cam_01 | Zone: 吊装区` 的警示横幅，并保存为标准快照文件；
- **标准路径契约**：统一存储至 `snapshots/YYYYMMDD/{event_uuid}.jpg`。

### 2.7 离线缓冲发布器 (OutboxStore & Publisher)
- **专用 Outbox 队列**：基于独立 SQLite 库，将待发事件加入 `outbox_events` 表；
- **网络容灾与指数退避**：当网络中断或 Agent 返回 5xx 时，按 $2^{\text{retry}}$ 执行退避重试；网络恢复后通过 `flush_outbox()` 自动补发；
- **致命错误熔断**：遇到 400/422 客户端格式错误时，自动标记为不可恢复终态并记录日志，避免无效死循环请求。

### 2.8 无头会话调度器与心跳守护 (SessionRunner)
- **多相机调度中枢 [`CivilSafetyPerceptionService`](file:///home/jjc/projects/python/civil_engineering_agent/perception/services/session_runner.py)**：支持多路流并发拉起与单独停机；
- **独立线程运行 [`CameraSessionRunner`](file:///home/jjc/projects/python/civil_engineering_agent/perception/services/session_runner.py)**：自动管理解码、推理、防抖状态与时间锚点；
- **周期性心跳**：每 5 秒滑动计算 FPS、在线工人数、安全帽合规率，定时上报 Agent；
- **配置在线轮询与优雅降级**：定时拉取最新围栏配置；若 Agent 配置端点暂不可用，**自动回退至本地默认配置，核心事件链路保持畅通**。

---

## 3. 智能体中枢子系统 (Agent) 功能详解

Agent 层代码位于 `agent/` 目录下，负责事件接收校验、业务主存入库、大模型（LLM）对话交互与安全日报编排。

### 3.1 FastAPI 契约层与 MySQL 事务持久化
- **API 路由规范**：
  - `/internal/v1/perception/events`：供 CV 调用的违规事件上报接口（基于 `event_uuid` 实现严格幂等的 UPSERT）；
  - `/internal/v1/perception/cameras/{camera_id}/status`：供 CV 调用的相机状态与心跳上报接口；
  - `/internal/v1/perception/cameras/{camera_id}/config`：供 CV 调用的围栏参数下发接口；
  - `/api/v1/safety/violations`：供前端或用户查询的安全违规列表查询接口；
  - `/api/v1/chat`：面向大模型的人机对话接口。
- **MySQL 关系主库**：通过 Alembic 进行数据库版本管理，管理摄像头、电子围栏、违规事件、日报任务等结构化数据。

### 3.2 围栏与摄像头在线配置管理
- 支持在 Agent 侧对每个摄像头配置专属的危险区域多边形、生效时段与防抖时间阈值；
- 配置带有单调自增的 `config_version`，CV 会话轮询到新版本即可实现**线上热更新**。

### 3.3 LangGraph 对话图与事实驱动原则
- **结构化图状态**：在 [`agent/graph/chat_graph.py`](file:///home/jjc/projects/python/civil_engineering_agent/agent/graph/chat_graph.py) 中定义显式状态流，包含意图分类、参数提取、工具调用、事实整合与回复生成；
- **证据链接地 (Evidence Grounding)**：对话系统检索出违规事实后，自动附带对应的 `event_uuid`、时间范围以及 `snapshot_uri`，供前端直接渲染点击查看现场照片。

### 3.4 LLM 适配器与多模型热切换 (DeepSeek)
- **协议端口 [`ChatModelPort`](file:///home/jjc/projects/python/civil_engineering_agent/agent/llm/protocol.py)**：定义统一的聊天接口契约；
- **DeepSeek 官方适配 [`DeepSeekChatModel`](file:///home/jjc/projects/python/civil_engineering_agent/agent/llm/deepseek_adapter.py)**：支持接入 DeepSeek-V3 / DeepSeek-R1 高性价比推理模型；
- **离线测试桩 [`FakeChatModel`](file:///home/jjc/projects/python/civil_engineering_agent/agent/llm/fake_adapter.py)**：在无网络、无 API Key 场景下保障全部单元测试与自动化流水线通过。

---

## 4. 快速上手与操作指南

### 4.1 环境准备与依赖安装

系统支持 Linux 与 Windows 运行，推荐 Python 3.10+。

```bash
# 1. 克隆进入工程目录
cd /home/jjc/projects/python/civil_engineering_agent

# 2. 安装感知层与智能体运行依赖
pip install -r requirements-agent.txt
```

---

### 4.2 感知子系统 CLI 命令行运行

无需启动任何窗口，即可在终端中运行视频流监控或生成日报。

#### 命令 1：启动监控流 (`run`)

```bash
# 场景 A：使用离线视频样例测试
python -m perception.cli run \
  --camera-id cam_gate_01 \
  --source tests/fixtures/sample_walk.mp4 \
  --agent-url http://127.0.0.1:8000 \
  --device auto

# 场景 B：接入施工现场 RTSP 高清监控流
python -m perception.cli run \
  --camera-id cam_tower_crane \
  --source "rtsp://admin:password@192.168.1.108:554/live" \
  --agent-url http://127.0.0.1:8000 \
  --device cuda:0 \
  --heartbeat-interval 5.0
```

> **操作提示**：按下 `Ctrl + C`，程序将捕获中断信号，安全释放视频流并向 Agent 报送下线状态后退出。

#### 命令 2：生成安全巡检日报数据 (`report`)

```bash
python -m perception.cli report --date 2026-09-25 --event-db data/events.db
```

终端将打印结构化的 JSON 统计数据（包含当日总违规数、各机位分布、违规类型占比与证据图 URI）。

---

### 4.3 感知子系统 GUI 桌面客户端运行

在有图形界面的开发机上，支持鼠标实时交互与绘制电子围栏。

```bash
python -m perception.gui.app
```

- **操作步骤**：
  1. 点击 **“Import”** 按钮选择视频或图片文件（例如 `tests/fixtures/sample_walk.mp4`）；
  2. 点击 **“Predict”** 按钮启动推理管道，系统自动加载 [`perception/configs/default_danger_zones.json`](../../perception/configs/default_danger_zones.json) 中定义的电子围栏并在画面上渲染红色警示框；
  3. 推理完成后，点击 **“Play”** 即可同步对比播放原视频与违规目标标注/电子围栏告警画面；
  4. 点击 **“Open in Browser”** 可直接打开推理生成的结果视频与违规证据快照目录。

---

### 4.4 启动 Agent 智能体后台服务

```bash
# 启动 FastAPI 服务 (开发模式)
python -m uvicorn agent.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，可在浏览器访问 `http://127.0.0.1:8000/docs` 查看交互式 Swagger API 文档。

---

### 4.5 CV 与 Agent 端到端全链路实操演练

完成以下三步即可体验完整的跨系统集成流水线：

```bash
# 步骤 1：后台启动 Agent API 服务
python -m uvicorn agent.main:app --port 8000 &

# 步骤 2：启动 CV 监控会话，灌入测试视频
python -m perception.cli run \
  --camera-id cam_field_01 \
  --source tests/fixtures/sample_walk.mp4 \
  --agent-url http://127.0.0.1:8000

# 步骤 3：查询 Agent 端是否成功入库事件与心跳
curl -X GET "http://127.0.0.1:8000/api/v1/safety/violations?camera_id=cam_field_01"
```

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
| `report` | `--date` | string | **必填** | 查询日期，支持 `YYYYMMDD` 或 `YYYY-MM-DD` |
| `report` | `--event-db` | string | `data/events.db` | 本地归档事件数据库路径 |

---

### 5.2 核心 REST API 清单

#### 1. 内部感知事件上报 (Internal Perception Events)
- **请求方法**：`POST /internal/v1/perception/events`
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
    "extra_details": {
      "helmet_compliance_rate": 0.8333
    }
  }
  ```

#### 3. 智能问答与安全分析 (Chat Agent API)
- **请求方法**：`POST /api/v1/chat`
- **请求体规格**：
  ```json
  {
    "query": "今天塔吊区有哪些严重的违规行为？",
    "session_id": "user_session_101"
  }
  ```
- **返回结果**：包含 LLM 回答正文、从数据库检索到的事实证据（`event_uuid`、时间戳、快照 URI）以及图执行审计摘要。

---

## 6. 自动化测试体系与质量验收

系统构建了高覆盖率的分层测试套件，杜绝回归缺陷。

```text
tests/
├── agent/                         # 智能体闭环测试套件 (9 项)
│   ├── test_camera_config_api.py  # 围栏配置下发与版本管理
│   ├── test_chat_closed_loop.py   # 智能问答全流程
│   ├── test_llm_factory.py        # 模型工厂与热切换
│   └── test_minimal_closed_loop.py # 最小闭环测试
└── perception/                    # 感知模块测试套件 (43 项)
    ├── test_cli.py                # 命令行工具解析与报告测试
    ├── test_detector_interface.py # 检测器适配器抽象
    ├── test_event_store.py        # 本地 SQLite 存储与快照验证
    ├── test_geometry.py           # 触地判定与坐标变换
    ├── test_integration_contract.py # 跨系统契约与 Outbox 验证
    ├── test_regression.py         # YOLO 双适配器回归推理
    ├── test_safety_pipeline.py    # 端到端感知流水线
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
> **验收基线**：**52 项测试全部通过（100% Pass）**，零错误、零破坏性变更。
