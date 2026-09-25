# Web 与 Agent 接口约定冻结契约 (Web-Agent Interface Freeze Contract)

> **版本**：v1.1.1 (FROZEN)  
> **冻结日期**：2026-09-25  
> **状态**：**已冻结 (Jointly Confirmed & Frozen)** —— Web 前端与 Agent 后端以此为唯一交付、实现与联调准绳。  
> **适用范围**：Web 前端工程、Agent 服务层 (`agent/api` / `agent/contracts`)。

---

## 0. 版本演进与变更对齐 (Change Log & Alignment)

### 0.1 v1.1.1 关键纠偏与联调校准
经过前后端深度对齐，v1.1.1 对以下 8 项核心工程问题进行了彻底纠偏与定稿：
1. **环境变量精准对齐**：纠正了文档前版与 Agent 真实实现不符的问题，严格采用 `agent/core/config.py` 中的原生变量（`AGENT_DATABASE_URL`, `INTERNAL_PERCEPTION_TOKEN`, `AGENT_LLM_PROVIDER` 等），并明确媒体配置项为 `AGENT_MEDIA_ROOT`。
2. **启动命令可执行性加固**：固定为 `python3 -m uvicorn agent.main:create_app --factory ...`，解决 Linux/容器环境中缺少 `python` 软链接的执行问题。
3. **接口实现状态显式标明**：在接口目录与详细章节中，明确标记【Agent 已就绪】与【待 Agent 端实现】，前端明确开发进度，避免误调报错。
4. **跨域策略 (CORS & Proxy)**：明确了开发环境优先采用 Vite `server.proxy` 反向代理同源访问，后端提供 `CORSMiddleware` 作为辅助兼容的双保险策略。
5. **摄像头“在线”与列表语义冻结**：定义 `GET /api/v1/cameras` 来源为已配置围栏与心跳上报相机的并集，30 秒未收心跳判定离线，结果按 `is_online DESC, camera_id ASC` 排序，Phase 1 全量不分页。
6. **媒体共享目录与 CV 对齐**：明确统一通过 `--snapshot-dir "$AGENT_MEDIA_ROOT"` 启动 CV，或指定公共存储目录，确保 CV 写入与 FastAPI 静态挂载同一物理路径。
7. **文档优先级确立**：明确本文档为 Web–Agent 间的最终准绳，`CV_Agent_Web_Integration_Contract.md` 已同步标注：本文优先，其监控启停接口为 Phase 2 预留。
8. **问答性能门禁客观测定 (GATE-06)**：修正硬编码 3 秒限制，采纳“本地 Fake 适配器/缓存 <= 3秒；外部真实 LLM 依 `AGENT_LLM_TIMEOUT_SECONDS`（默认 20s）执行降级”的客观标准。

---

## 1. 背景与协作原则

### 1.1 背景说明
本项目中，**Web 前端开发**与 **Agent 后端开发**由专人分工负责。为了确保双方**并行推进、互不阻塞、零冲突协作**，特制定本约定冻结文档。

### 1.2 协作与解耦原则
1. **契约即代码 (Contract-First)**：
   - 所有的 HTTP 路由、请求参数、响应体结构、错误码及数据语义均已在本契约中明确固化。
   - 双方以此文档为法定接口边界，未走契约变更流程前，任何一方不得擅自改动字段名、增删必填项或变更类型。
2. **前后端独立闭环 (Zero Blocking)**：
   - **Web 前端**：采用 **Vue 3 + Vite + TypeScript + 现代 UI 生态（Element Plus / ECharts / Konva.js / markdown-it 等）**，坚持成熟组件化装配，**决不自己手搓基础轮子**。基于本文档第 5 章提供的 TypeScript 类型定义与第 7 章的 Mock 桩数据独立开发全部 UI 组件、标定画布、看板统计及智能问答界面。即使 Agent 后端未启动、数据库未就绪，前端亦可 100% 验证视觉与交互逻辑。
   - **Agent 后端**：聚焦于 LangGraph 编排、LLM 适配、MySQL 事务、工具注册及与 CV 层的事件入库，通过自动化单元测试 (`tests/agent/`) 保证返回结构严格契合本契约。
3. **联调无缝切换**：
   - 前端通过环境变量 `VITE_USE_MOCK=true/false` 切换 Mock 与真实接口，联调时仅需配置后端服务地址即可完成闭环。

---

## 2. 职责边界矩阵

| 模块 / 领域 | Web 前端负责范围 | Agent 后端负责范围 | 共同遵守 / 严格禁止 |
|---|---|---|---|
| **界面与交互** | 1. 响应式控制台、监控矩阵大屏<br>2. 违规事件卡片流与筛选器<br>3. 违规统计图表 (ECharts)<br>4. 智能安全问答 Copilot 对话框<br>5. 证据截图查看与目标框高亮 | 提供 OpenAPI / Swagger 接口规范，维护服务端稳定性 | 前端不直连数据库、不直连 CV 节点；后端不参与界面样式与 DOM 编排 |
| **危险区域标定** | 1. Canvas / SVG 危险区域多边形交互绘制<br>2. 屏幕显示像素与原始视频帧像素的双向映射反算<br>3. 遇到 404 启动首次创建模式；遇到 409 拦截版本冲突提示并重拉取 | 1. 围栏几何顶点格式校验（>=3 点）<br>2. 维护自增 `config_version`<br>3. 乐观锁检测 (409 Conflict)<br>4. 下发给 CV 运行层 | **坐标系统必须使用视频原始帧绝对像素**，禁止将前端屏幕 CSS 像素存入数据库或下发 CV |
| **智能安全问答** | 1. 对话流气泡与 Markdown 解析<br>2. 工具调用链路 (Tool Trace) 折叠展示<br>3. 结构化证据卡片 (Evidence) 渲染与跳转 | 1. LangGraph 意图理解与工具调用<br>2. 违规与相机数据受限读取<br>3. 汇总成答案并生成结构化证据与耗时审计 | **不向前端暴露模型原始思维链 (CoT)**；前端仅展示 `answer`、`evidence` 与 `tool_trace` |
| **媒体证据展示** | 根据 `snapshot_uri` 拼接 `/media/${snapshot_uri}` 渲染图片 | 挂载静态媒体服务路径，由 `AGENT_MEDIA_ROOT` 提供本地文件映射 | 禁止传递/依赖仅在 CV 主机本地有效的操作系统绝对物理路径 |
| **视频流与启停** | 轮询摄像头在线状态与 FPS，展示监控矩阵卡片与推流画面 | 记录摄像头心跳与状态上报；Phase 1 监控启停由后台或测试脚本托管 | Phase 1 不将启停作为阻塞接口，Phase 2 待调度器就绪后提供 |

---

## 3. 全局通信、跨域与媒体规范

### 3.1 协议与编码
- **协议**：HTTP/1.1 或 HTTP/2 (RESTful JSON)
- **Base URL**：`/api/v1`
- **字符编码**：`UTF-8`
- **Content-Type**：`application/json`

### 3.2 时间与时区标准
- **所有传输的时间字段必须采用 ISO 8601 UTC 字符串**，形如：`2026-09-25T10:30:00Z`。
- 后端保证返回的时间统一为 UTC 时区，且带 `Z` 或 `+00:00` 明确标示。
- 前端接收后，统一负责根据用户现场时区（默认 `UTC+8 / Asia/Shanghai`）转换为本地可读字符串展示。

### 3.3 统一错误响应规范
统一采用标准 FastAPI 的原生错误结构：

```json
{
  "detail": "camera cam_crane_01 config version mismatch: expected 3, found 4"
}
```
*注：遇到参数或 Pydantic 校验失败时，HTTP 状态码为 `422 Unprocessable Entity`，`detail` 为字段错误对象列表。*

### 3.4 跨域策略 (CORS & Proxy)
为支持 Web 开发服务器（如 Vite 默认 `http://localhost:5173`）与 Agent 服务（`http://localhost:8000`）顺利通信，约定以下双重跨域方案：
1. **前端工程开发首选方案（Vite 反向代理）**：
   在 `vite.config.ts` 中配置同源代理，前端代码无需感知跨域，直接请求 `/api` 与 `/media`：
   ```typescript
   export default defineConfig({
     server: {
       proxy: {
         '/api': {
           target: 'http://127.0.0.1:8000',
           changeOrigin: true,
         },
         '/media': {
           target: 'http://127.0.0.1:8000',
           changeOrigin: true,
         }
       }
     }
   });
   ```
2. **后端辅助兜底方案（CORS 中间件）**：
   Agent 已挂载 `CORSMiddleware`，开放 `http://localhost:5173` 与 `http://127.0.0.1:5173`，`allow_methods=["*"]`, `allow_headers=["*"]`。

### 3.5 媒体资源存储与访问策略 (Media Strategy)
1. **配置项定义**：
   - Agent 后端增加环境配置项：`AGENT_MEDIA_ROOT`（默认值：`./runs/media`，亦可指向 `./data/snapshots`）。
2. **挂载与访问路径**：
   - Agent 后端使用 FastAPI 静态目录服务挂载：
     ```python
     app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
     ```
   - 前端通过 `GET /media/{snapshot_uri}` 访问快照（如：`http://127.0.0.1:8000/media/snapshots/20260925/a5d10bde.jpg`）。
3. **与 CV 感知层配置对齐**：
   - CV 模块启动时，统一指定快照目录与 Agent 媒体根目录一致：
     `python3 -m perception.cli run --snapshot-dir "$AGENT_MEDIA_ROOT" ...`
   - CV 自动归档至 `${AGENT_MEDIA_ROOT}/snapshots/YYYYMMDD/<uuid>.jpg`，向 Agent 提交的事件中 `snapshot_uri` 统一填写标准相对路径 `snapshots/YYYYMMDD/<uuid>.jpg`。
4. **鉴权与 404 表现**：
   - **免密访问**：第一期/比赛期 `/media` 静态资源为公开只读，便于前端 `<img src="...">` 直接加载展示。
   - **404 表现**：文件若在磁盘上不存在，由静态服务返回标准 `404 Not Found`。Web 端统一捕获 `onerror` 并渲染“快照丢失/暂无证据”占位图标。

---

## 4. API 接口详细契约与落地状态

| 方法 | 路径 | 功能说明 | 状态 | 联调说明 |
|---|---|---|---|---|
| `GET` | `/api/v1/cameras` | 查询全量摄像头看板矩阵 | **【Agent 已就绪】** | 可切换真实接口联调 |
| `GET` | `/api/v1/cameras/{camera_id}/status` | 查询指定摄像头推流与心跳状态 | **【Agent 已就绪】** | 404 表示离线或尚未上报 |
| `GET` | `/api/v1/violations` | 分页检索违规记录列表 | **【Agent 已就绪】** | 返回 `ViolationPageResponse` |
| `GET` | `/api/v1/violations/statistics` | 查询违规统计分析数据 | **【Agent 已就绪】** | 前端 TS 兼容键值缺省 |
| `GET` | `/api/v1/cameras/{camera_id}/zones` | 查询摄像头生效围栏与版本号 | **【Agent 已就绪】** | 404 表示未标定，前端切首次创建 |
| `PUT` | `/api/v1/cameras/{camera_id}/zones` | 更新摄像头危险区域与参数 | **【Agent 已就绪】** | 支持 `expected_version` 乐观并发控制 |
| `POST` | `/api/v1/agent/chat` | 智能安全问答 (Copilot) | **【Agent 已就绪】** | 返回结论、证据卡片与工具调用链 |
| `GET` | `/media/{snapshot_uri}` | 静态抓拍证据媒体加载 | **【Agent 已就绪】** | 由 `AGENT_MEDIA_ROOT` 托管 |
| `POST` | `/api/v1/cameras/{id}/monitoring:start` | 启动摄像头监控 | **【Phase 2 预留】** | 本期不阻塞，推流状态以心跳为准 |
| `POST` | `/api/v1/cameras/{id}/monitoring:stop` | 停止摄像头监控 | **【Phase 2 预留】** | 本期不阻塞，推流状态以心跳为准 |

---

### 4.1 摄像头列表接口 (多摄监控矩阵看板)
- **实现状态**：**【Agent 已就绪】**
- **路径**：`GET /api/v1/cameras`
- **说明**：查询系统中已注册或已上报状态的摄像头列表。
- **数据来源与业务规则**：
  1. **数据并集**：包含所有在 `camera_configs` 表中有围栏记录的相机，以及在 `camera_status` 中曾上报过心跳的相机。
  2. **在线判定**：若 `(当前UTC时间 - reported_at_utc) <= 30秒`，判定为 `is_online: true`；否则为 `false`。
  3. **排序规则**：按 `is_online DESC, camera_id ASC` 排序（在线相机优先展示，同状态按 ID 字母排序）。
  4. **分页策略**：Phase 1 现场摄像头通常在 10~50 路以内，列表不分页，直接返回全量数组。
- **响应格式 (200 OK)**：`list[CameraStatusResponse]`
```json
[
  {
    "camera_id": "cam_crane_01",
    "monitor_session_id": "run_20260925_001",
    "is_online": true,
    "fps": 24.8,
    "processed_frame_id": 142857,
    "active_workers_count": 2,
    "model_name": "helmet_head_person_m",
    "model_version": "legacy-yolov5",
    "reported_at_utc": "2026-09-25T10:35:00Z",
    "extra_details": {}
  }
]
```

---

### 4.2 单摄像头运行状态查询
- **实现状态**：**【Agent 已就绪】**
- **路径**：`GET /api/v1/cameras/{camera_id}/status`
- **Path 参数**：`camera_id` (string)
- **响应格式 (200 OK)**：单个 `CameraStatusResponse`。
- **异常响应**：
  - `404 Not Found`：`{"detail": "camera status not found"}`。

---

### 4.3 违规事件检索列表 (统一标准分页)
- **实现状态**：**【Agent 已就绪】**
- **路径**：`GET /api/v1/violations`
- **Query 参数**：
  | 参数名 | 类型 | 必填 | 默认值 | 约束 / 说明 |
  |---|---|---|---|---|
  | `camera_id` | string | 否 | null | 摄像头编号（如 `cam-a01`） |
  | `violation_type` | string | 否 | null | 枚举：`NO_HELMET`, `DANGER_ZONE_INTRUSION`, `DWELL_TIMEOUT` |
  | `severity` | string | 否 | null | 枚举：`INFO`, `WARNING`, `CRITICAL` |
  | `status` | string | 否 | null | 枚举：`ACTIVE`, `RESOLVED`, `FALSE_ALARM` |
  | `start_time_utc` | string | 否 | null | 起始时间 (ISO 8601 UTC) |
  | `end_time_utc` | string | 否 | null | 截止时间 (ISO 8601 UTC) |
  | `limit` | integer | 否 | 100 | 单页大小 (1 <= limit <= 500) |
  | `offset` | integer | 否 | 0 | 偏移量 (offset >= 0) |

- **响应格式 (200 OK)**：`ViolationPageResponse`
```json
{
  "items": [
    {
      "event_uuid": "a5d10bde-ef52-4ef7-8471-50b74c864623",
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
      "duration_seconds": 15.5,
      "snapshot_uri": "snapshots/20260925/a5d10bde.jpg",
      "model_name": "helmet_head_person_m",
      "model_version": "legacy-yolov5",
      "extra_details": {
        "dwell_threshold_seconds": 5.0,
        "bbox": [120.0, 90.0, 280.0, 500.0],
        "feet_point": [200.0, 500.0]
      }
    }
  ],
  "total": 128,
  "limit": 100,
  "offset": 0
}
```

---

### 4.4 违规态势综合统计
- **实现状态**：**【Agent 已就绪】**
- **路径**：`GET /api/v1/violations/statistics`
- **Query 参数**：`camera_id`, `start_time_utc`, `end_time_utc`
- **响应格式 (200 OK)**：
```json
{
  "total_violations": 42,
  "average_duration_seconds": 18.4,
  "by_type": {
    "NO_HELMET": 15,
    "DANGER_ZONE_INTRUSION": 22
  },
  "by_severity": {
    "WARNING": 25,
    "CRITICAL": 12
  }
}
```

---

### 4.5 危险区域标定与相机配置

#### 4.5.1 读取当前配置
- **实现状态**：**【Agent 已就绪】**
- **路径**：`GET /api/v1/cameras/{camera_id}/zones`
- **正常响应格式 (200 OK)**：
```json
{
  "camera_id": "cam_crane_01",
  "config_version": 3,
  "source_resolution": {
    "width": 1920,
    "height": 1080
  },
  "enter_debounce_frames": 3,
  "exit_debounce_frames": 5,
  "helmet_debounce_frames": 5,
  "alarm_dwell_threshold_seconds": 5.0,
  "zones": [
    {
      "zone_id": "zone_crane_operational",
      "zone_name": "吊装禁行区",
      "polygon": [
        [402.0, 234.0],
        [497.0, 182.0],
        [727.0, 432.0],
        [364.0, 456.0]
      ],
      "enabled": true,
      "alarm_dwell_threshold_seconds": 5.0
    }
  ]
}
```
- **配置不存在时的行为**：
  - 状态码：`404 Not Found`，响应体：`{"detail": "camera config not found"}`
  - **前端处理规范**：前端捕获 404 后进入“首次创建”模式，初始化默认模板（1920×1080，`zones: []`，默认防抖参数），首次保存时传 `expected_version: null`。

#### 4.5.2 更新配置（带乐观并发控制）
- **实现状态**：**【Agent 已就绪】**
- **路径**：`PUT /api/v1/cameras/{camera_id}/zones`
- **请求体格式**：
```json
{
  "expected_version": 3,
  "source_resolution": {
    "width": 1920,
    "height": 1080
  },
  "enter_debounce_frames": 3,
  "exit_debounce_frames": 5,
  "helmet_debounce_frames": 5,
  "alarm_dwell_threshold_seconds": 5.0,
  "zones": [
    {
      "zone_id": "zone_crane_operational",
      "zone_name": "吊装禁行区",
      "polygon": [
        [402.0, 234.0],
        [497.0, 182.0],
        [727.0, 432.0],
        [364.0, 456.0]
      ],
      "enabled": true,
      "alarm_dwell_threshold_seconds": 5.0
    }
  ]
}
```
- **成功响应 (200 OK)**：返回递增后的 `CameraRunConfigV1`。
- **并发冲突异常 (409 Conflict)**：
  - 触发条件：`expected_version` 与服务端当前版本不一致。
  - 响应体：`{"detail": "camera cam_crane_01 config version mismatch: expected 3, found 4"}`。
  - 前端处理原则：拦截 409，提示用户重新加载最新版本。

---

### 4.6 智能安全问答 (Agent Copilot Chat)
- **实现状态**：**【Agent 已就绪】**
- **路径**：`POST /api/v1/agent/chat`
- **请求体格式**：
```json
{
  "question": "今天 A01 摄像头有多少严重违规？最近一条是什么？",
  "conversation_id": "session-web-20260925-001"
}
```
- **响应格式 (200 OK)**：
```json
{
  "request_id": "req-98835df7-e6f7-4638-b7eb-12502ee6d833",
  "answer": "今天 cam-a01 摄像头共检测到 3 起 CRITICAL 级别严重违规。最近一条发生在 14:22:10，为吊装作业区人员闯入（违规类型：DANGER_ZONE_INTRUSION）。",
  "evidence": [
    {
      "event_uuid": "a5d10bde-ef52-4ef7-8471-50b74c864623",
      "occurred_at_utc": "2026-09-25T06:22:10Z",
      "snapshot_uri": "snapshots/20260925/a5d10bde.jpg"
    }
  ],
  "tool_trace": [
    {
      "tool_name": "get_violation_statistics",
      "success": true,
      "purpose": "查询 cam-a01 今日严重违规总数",
      "duration_ms": 12
    },
    {
      "tool_name": "query_violations",
      "success": true,
      "purpose": "查询最近一条严重违规详情与快照",
      "duration_ms": 18
    }
  ],
  "degraded": false,
  "error_code": null
}
```

---

## 5. 前端 TypeScript 契约定义 (Single Source of Truth)

Web 前端工程（`src/types/contract.ts`）严格采用以下类型定义：

```typescript
export type ViolationType = "NO_HELMET" | "DANGER_ZONE_INTRUSION" | "DWELL_TIMEOUT";
export type ViolationSeverity = "INFO" | "WARNING" | "CRITICAL";
export type EventStatus = "ACTIVE" | "RESOLVED" | "FALSE_ALARM";

export interface SourceResolution {
  width: number;
  height: number;
}

export interface DangerZoneConfig {
  zone_id: string;
  zone_name: string;
  polygon: [number, number][]; // 顶点 >= 3 个点，每个点为 [x, y] 原始物理像素
  enabled: boolean;
  alarm_dwell_threshold_seconds: number;
}

export interface CameraRunConfig {
  camera_id: string;
  config_version: number;
  source_resolution: SourceResolution;
  enter_debounce_frames: number;
  exit_debounce_frames: number;
  helmet_debounce_frames: number;
  alarm_dwell_threshold_seconds: number;
  zones: DangerZoneConfig[];
}

export interface CameraConfigUpdateRequest {
  expected_version?: number | null;
  source_resolution: SourceResolution;
  enter_debounce_frames: number;
  exit_debounce_frames: number;
  helmet_debounce_frames: number;
  alarm_dwell_threshold_seconds: number;
  zones: DangerZoneConfig[];
}

export interface ViolationRecord {
  event_uuid: string;
  camera_id: string;
  monitor_session_id: string;
  track_id: number;
  violation_type: ViolationType;
  severity: ViolationSeverity;
  status: EventStatus;
  zone_id: string | null;
  zone_name: string | null;
  occurred_at_utc: string; // ISO 8601 UTC
  resolved_at_utc: string | null;
  duration_seconds: number;
  snapshot_uri: string | null;
  model_name: string | null;
  model_version: string | null;
  extra_details: {
    dwell_threshold_seconds?: number;
    bbox?: [number, number, number, number]; // [x1, y1, x2, y2] 绝对像素坐标
    feet_point?: [number, number];          // [x, y] 脚底接地点像素坐标
    [key: string]: any;
  };
}

export interface ViolationPageResponse {
  items: ViolationRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ViolationStatistics {
  total_violations: number;
  average_duration_seconds: number;
  by_type: Partial<Record<ViolationType, number>>;
  by_severity: Partial<Record<ViolationSeverity, number>>;
}

export interface CameraStatusResponse {
  camera_id: string;
  monitor_session_id: string;
  is_online: boolean;
  fps: number;
  processed_frame_id: number;
  active_workers_count: number;
  model_name: string | null;
  model_version: string | null;
  reported_at_utc: string;
  extra_details: Record<string, any>;
}

export interface ChatEvidence {
  event_uuid: string;
  occurred_at_utc: string;
  snapshot_uri: string | null;
}

export interface ToolTraceItem {
  tool_name: "query_violations" | "get_violation_statistics" | "get_camera_status";
  success: boolean;
  purpose: string;
  duration_ms: number;
}

export interface ChatRequest {
  question: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  request_id: string;
  answer: string;
  evidence: ChatEvidence[];
  tool_trace: ToolTraceItem[];
  degraded: boolean;
  error_code?: string | null;
}

export interface ApiErrorResponse {
  detail: string | Array<{ loc: (string | number)[]; msg: string; type: string }>;
}
```

---

## 6. 物理坐标系与前端视口变换规范

```text
+------------------------------------------------------------+
| 原始视频物理帧 (e.g. 1920 x 1080)                           |
|   (x_video, y_video) ------------------+                   |
|                                        |                   |
+----------------------------------------|-------------------+
                                         | 缩放比 scale = display / source
                                         v
+------------------------------------------------------------+
| Web 前端 Canvas / 视口呈现 (e.g. 960 x 540)                |
|   (x_canvas, y_canvas) = (x_video * scaleX, y_video * scaleY)
+------------------------------------------------------------+
```

1. **绝对基准**：
   - 契约中的 `polygon` 顶点坐标与 `bbox`、`feet_point` **始终且仅使用原始视频分辨率物理像素**（由 `source_resolution` 声明，如 1920×1080）。
2. **Web 端渲染变换（正向投影）**：
   - 当前端画布宽高为 `(W_disp, H_disp)` 时：
     $$\text{scaleX} = \frac{W_{\text{disp}}}{W_{\text{source}}}, \quad \text{scaleY} = \frac{H_{\text{disp}}}{H_{\text{source}}}$$
     $$\text{point}_{\text{disp}} = [x_{\text{video}} \times \text{scaleX}, \ y_{\text{video}} \times \text{scaleY}]$$
3. **用户绘制保存（逆向投影）**：
   - 用户在浏览器上点击或拖拽得到的坐标点 `[x_disp, y_disp]`，必须在提交前除以对应缩放比，并取整保存：
     $$\text{point}_{\text{video}} = \left[ \text{round}\left(\frac{x_{\text{disp}}}{\text{scaleX}}\right), \ \text{round}\left(\frac{y_{\text{disp}}}{\text{scaleY}}\right) \right]$$
   - 确保无论用户在 4K 屏、1080P 屏或平板浏览器上标定，提交给后端的几何形状在物理视频流中始终完全一致。

---

## 7. Web 前端独立 Mock 开发机制

### 7.1 Mock 开关设计
在 Web 前端配置 `.env.development`：
```bash
# true 表示前端拦截全部请求并直接返回本地 Mock 数据；false 表示请求真实后端
VITE_USE_MOCK=true
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 7.2 Mock 桩响应数据集 (Fixtures)
前端工程提供本地模拟服务，并预置以下典型测试数据集：
1. **多摄像头列表与状态**：包含在线（正常 25fps）、告警、离线等状态。
2. **典型违规事件分页列表**：包含 `items`, `total: 128`, `limit: 100`, `offset: 0`。
3. **Agent Copilot 对话交互场景**：包含正常查询、超纲问题、降级模式（`degraded=true`）。
4. **并发冲突场景**：模拟更新配置时返回 `409 Conflict`，验证前端冲突提示与重拉取逻辑。
5. **未标定相机 404**：模拟首次配置摄像头的交互流程。

---

## 8. Agent 运行方式与环境变量固定 (Run & Env Standards)

### 8.1 Agent 启动命令固定
在调试与联调运行 Agent 服务时，统一使用带 Python 模块调用与工厂模式参数的命令启动：

```bash
python3 -m uvicorn agent.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### 8.2 Agent 真实环境变量清单 (`.env`)
严格对应 `agent/core/config.py` 中的原生变量定义：

| 变量名 | 必填 | 示例值 | 说明 |
|---|---|---|---|
| `AGENT_DATABASE_URL` | 是 | `sqlite+pysqlite:///./agent.db` 或 `mysql+pymysql://...` | 数据库连接字符串 |
| `INTERNAL_PERCEPTION_TOKEN` | 是 | `perception-insecure-token` | CV 层调用内部接口的 Bearer 密钥 |
| `AGENT_MEDIA_ROOT` | 否 | `./runs/media` | 证据截图存储根目录，映射到 `/media/`；未设置时使用该默认值 |
| `AGENT_LLM_PROVIDER` | 否 | `fake` 或 `deepseek` | LLM 提供方，默认 `fake` |
| `AGENT_LLM_MODEL` | 否 | `deepseek-flash` | 模型名称 |
| `AGENT_LLM_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek API 地址 |
| `AGENT_LLM_API_KEY` | 否 | `sk-...` | 当 provider 为 deepseek 时必填 |
| `AGENT_LLM_TIMEOUT_SECONDS` | 否 | `20.0` | LLM 交互超时时间（秒） |
| `AGENT_TOOL_MAX_CALLS` | 否 | `2` | 单次问答允许的最大工具调用次数 |
| `AGENT_AUTO_CREATE_SCHEMA` | 否 | `true` | 是否启动时自动创建 SQLite/MySQL 数据表 |

### 8.3 本地代理绕过设置 (Proxy Bypass)
开发机通常配置有系统级网络代理（如科学上网或公司网关）。为防止本地开发时 Web 前端向 `127.0.0.1:8000` 发起的 API 请求或 Agent 服务间内部通信被系统代理劫持导致 `502 Bad Gateway` 或 `Connection Refused`，必须在终端或系统环境中配置 `no_proxy`：

```bash
export no_proxy="localhost,127.0.0.1,::1"
export NO_PROXY="localhost,127.0.0.1,::1"
```

---

## 9. 联调验证门禁 (Integration Gateways)

| 门槛编号 | 验收项 | 验证操作 | 预期结果 |
|---|---|---|---|
| **GATE-01** | 摄像头多摄矩阵 | Web 打开监控首页，请求 `GET /api/v1/cameras` | 渲染多摄像头状态矩阵，在线/离线徽标准确 |
| **GATE-02** | 事件分页与筛选 | Web 筛选 `severity=CRITICAL`，翻页切换 | `ViolationPageResponse` 正确更新，Element Plus 分页条总量一致 |
| **GATE-03** | 证据大图免密访问 | 点击任一违规事件卡片查看大图 | 成功从 `/media/{snapshot_uri}` 载入图片，Canvas 精确绘制 `bbox` |
| **GATE-04** | 围栏读取与首次创建 | 读取未标定相机配置 | 正确处理 404，进入默认新围栏标定，保存时成功生成版本 1 |
| **GATE-05** | 乐观锁并发拦截 | 两端修改同一版本配置并保存 | 后提交端准确拦截 409 Conflict，提示用户刷新重试 |
| **GATE-06** | Agent 智能问答时延 | 输入：“今天 A01 摄像头有多少严重违规？” | 本地 Fake 模型/缓存应在 **3 秒内**返回；外部真实 LLM 依 `AGENT_LLM_TIMEOUT_SECONDS`（默认 20s）执行，超时平滑降级（`degraded=true`） |
