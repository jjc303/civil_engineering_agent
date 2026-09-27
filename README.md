# 智慧施工安全智能体

面向施工现场的视频安全管理系统。项目把 CV 识别、违规事件、摄像头控制、知识库检索（RAG）、安全问答和整改闭环放在同一套前后端中；所有会改变现场状态或业务数据的 Agent 操作，均先生成页面待确认操作，再由用户确认执行。

## 1. 项目结构与技术栈

```text
.
├── agent/                         # FastAPI Agent 服务
│   ├── api/                       # 问答、事件、摄像头、知识库、整改任务接口
│   ├── contracts/                 # Pydantic 请求/响应契约
│   ├── db/                        # SQLAlchemy 模型与 Alembic 迁移
│   ├── graph/                     # Agent 多步工具规划图
│   ├── llm/                       # DeepSeek / Fake 模型适配器
│   ├── rag/                       # Chroma 检索与 Embedding 适配器
│   ├── services/                  # 领域服务、写操作确认、整改任务服务
│   └── tools/                     # Agent 可调用的只读工具
├── perception/                    # CV 推理、跟踪、危险区域与控制节点
├── web/                           # Vue 3 前端
├── scripts/start_stack.sh         # 一键启动 API、Web 与本地 CV 控制节点
├── tests/                         # Agent 与感知模块测试
├── docs/                          # 接口契约、设计和迁移说明
└── runs/                          # 运行时日志、快照、知识库原文、Chroma 向量库
```

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.10+、FastAPI、Uvicorn、Pydantic、SQLAlchemy、Alembic |
| 业务数据库 | MySQL 8（开发测试也可用 SQLite 内存库） |
| Agent | LangGraph、DeepSeek API、短期会话记忆、工具调用与重试 |
| RAG | ChromaDB、阿里云百炼 DashScope `text-embedding-v4`、`pypdf`、`python-docx` |
| CV | PyTorch、Ultralytics、OpenCV、目标跟踪、危险区域几何判断 |
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Element Plus、ECharts、Konva |

运行拓扑：

```text
浏览器 (Vue :5173)
        │
        ▼
Agent API (FastAPI :8000) ── MySQL
        │       │                │
        │       ├── Chroma + 文档目录（RAG）
        │       └── DeepSeek（推理/工具规划）
        │
        ▼
本地 CV 控制节点 (:8100) ── 摄像头 / 视频文件 / RTSP
```

## 2. 项目功能

### 现场安全与视频

- 摄像头与 CV 节点注册、节点在线状态、视频源配置、启停监控。
- MJPEG 实时预览输出标注帧：人员框、头盔状态、危险区域、违规/告警文字。
- 危险区域多边形标定与下发；支持危险区域入侵、危险区域停留超时、未佩戴安全帽等违规事件。
- 违规事件中心支持筛选、统计、状态查看和违规快照预览。
- 违规证据快照存放在 `runs/media/snapshots/`，通过 Agent 的 `/media` 路径供浏览器访问。

### 安全智能助手

- 使用 DeepSeek 进行意图判断、工具选择和最多两步的工具闭环；工具返回错误或参数不完整时会把结果回传模型再次决策。
- 可查询现场作业人数、摄像头状态、违规事件、知识库等数据。
- 目标不明确时，可展示可点击的摄像头或违规事件选项，而非硬编码名称。
- 支持浏览器会话短期记忆；默认保留 24 小时；工具轨迹在页面中可审计。

### 文档知识库（RAG）

- 支持 `.pdf`、`.docx`、`.md`、`.txt` 文档切分、向量化、检索和引用。
- 直接把文件放入 `runs/knowledge/inbox/`；启动时及后续定时同步会自动入库，无需管理员令牌。
- 默认使用阿里云百炼 DashScope OpenAI 兼容接口和 `text-embedding-v4`；向量数据持久化到 `runs/chroma/`。
- 同时提供知识文档、版本与索引任务接口，便于接入管理后台。

### 整改任务闭环

- 整改任务中心支持按状态、负责人、是否逾期筛选与分页查看。
- 可从**活动违规**手工创建关联整改任务，填写整改要求、负责人、截止时间和说明。
- 可查看任务详情、关联违规证据图和任务操作审计。
- 修改、完成、取消都会先生成待确认操作；确认后才写入数据库。
- 完成整改任务会同步把关联违规标记为已解决；取消任务不会关闭违规。
- 已完成或已取消的任务是终态：页面只可查看详情，后端也会拒绝生成更新确认操作。

### 安全边界

- CV 到 Agent 的内部事件接口使用 `INTERNAL_PERCEPTION_TOKEN` 鉴权。
- CV 节点注册、摄像头配置和启停由 `AGENT_ADMIN_TOKEN` 保护；RAG 收件目录、智能助手和整改任务接口不需要管理员令牌。
- 摄像头源地址与控制令牌不返回浏览器；写操作采用“提议 → 用户确认 → 服务端执行”的模式，并保留审计记录。

## 3. 从零开始运行

### 3.1 前置条件

- Python 3.10 或更高版本。
- Node.js 20 或更高版本，npm。
- MySQL 8.0（推荐）并已启动。示例配置使用宿主机 `127.0.0.1:3307`；按实际端口修改。
- 可选：NVIDIA GPU、CUDA、可访问的摄像头/RTSP 地址。没有 GPU 时可使用视频文件演示。
- 可访问 DeepSeek（Agent）和阿里云百炼（启用 RAG 时）的网络。

### 3.2 创建数据库

先在 MySQL 创建数据库（账号、密码和端口替换为自己的值）：

```sql
CREATE DATABASE safety_agent
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

### 3.3 安装依赖

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-agent.txt

cd web
npm ci
cd ..
```

> `requirements.txt` 包含 CV/PyTorch/Ultralytics 依赖，首次安装可能较大。若使用 GPU，请按本机 CUDA 版本安装匹配的 PyTorch，再安装其余依赖。

### 3.4 配置 `.env`

复制模板，不要提交真实的 `.env`：

```bash
cp .env.example .env
```

以下是单机开发可直接参考的配置。把所有 `REPLACE_...`、路径和地址替换为真实值；令牌建议用 `openssl rand -hex 32` 生成。

```dotenv
# MySQL
AGENT_DATABASE_URL=mysql+pymysql://root:REPLACE_WITH_DATABASE_PASSWORD@127.0.0.1:3307/safety_agent?charset=utf8mb4

# 服务监听与跨域；局域网部署时替换为实际 IP/DNS
AGENT_BIND_HOST=0.0.0.0
AGENT_PORT=8000
AGENT_URL=http://127.0.0.1:8000
AGENT_CORS_ORIGINS=http://127.0.0.1:5173
WEB_BIND_HOST=0.0.0.0
WEB_PORT=5173

# 内部 CV 与管理接口的密钥；不要填写到浏览器页面中
INTERNAL_PERCEPTION_TOKEN=REPLACE_WITH_A_RANDOM_SECRET
AGENT_ADMIN_TOKEN=REPLACE_WITH_A_RANDOM_SECRET
CV_NODE_TOKEN=REPLACE_WITH_A_RANDOM_SECRET
AGENT_CREDENTIAL_ENCRYPTION_KEY=REPLACE_WITH_FERNET_KEY

# Agent 大模型；临时演示可改为 fake，且 AGENT_LLM_API_KEY 可留空
AGENT_LLM_PROVIDER=deepseek
AGENT_LLM_MODEL=deepseek-flash
AGENT_LLM_BASE_URL=https://api.deepseek.com
AGENT_LLM_API_KEY=REPLACE_WITH_DEEPSEEK_API_KEY
AGENT_LLM_TIMEOUT_SECONDS=20
AGENT_TOOL_MAX_CALLS=2
AGENT_AUTO_CREATE_SCHEMA=false

# 会话记忆
AGENT_MEMORY_ENABLED=true
AGENT_MEMORY_TTL_HOURS=24
AGENT_MEMORY_RECENT_TURNS=6

# RAG；设为 false 时无需 DashScope Key
AGENT_RAG_ENABLED=true
AGENT_RAG_PERSIST_DIRECTORY=./runs/chroma
AGENT_RAG_DOCUMENT_DIRECTORY=./runs/knowledge
AGENT_RAG_INBOX_DIRECTORY=./runs/knowledge/inbox
AGENT_RAG_SYNC_INTERVAL_SECONDS=30
AGENT_RAG_EMBEDDING_PROVIDER=dashscope
AGENT_RAG_EMBEDDING_MODEL=text-embedding-v4
AGENT_RAG_EMBEDDING_API_KEY=REPLACE_WITH_DASHSCOPE_API_KEY
AGENT_RAG_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
AGENT_RAG_EMBEDDING_DIMENSIONS=1024
AGENT_RAG_CHUNK_SIZE=800
AGENT_RAG_CHUNK_OVERLAP=120
AGENT_RAG_TOP_K=4
AGENT_RAG_TOP_K_MAX=8
AGENT_RAG_MAX_UPLOAD_BYTES=20971520
AGENT_RAG_ALLOWED_EXTENSIONS=.pdf,.docx,.md,.txt

# 本地 CV 控制节点和演示摄像头
CV_BIND_HOST=0.0.0.0
CV_CONTROL_PORT=8100
CV_NODE_ID=cv-node-local-01
CV_NODE_DISPLAY_NAME=本地CV节点
CV_NODE_CONTROL_URL=http://127.0.0.1:8100
CV_NODE_CAPACITY=1
CV_ALLOWED_MEDIA_ROOTS=/absolute/path/to/allowed/media
AGENT_MEDIA_ROOT=./runs/media
CV_SNAPSHOT_DIR=./runs/media/snapshots
LOCAL_CAMERA_ID=cam_field_01
LOCAL_CAMERA_DISPLAY_NAME=现场主摄像头
LOCAL_CAMERA_SOURCE_TYPE=file
LOCAL_CAMERA_SOURCE=/absolute/path/to/demo.mp4
```

说明：

- `AGENT_ADMIN_TOKEN` 只供启动脚本注册本地 CV 节点和摄像头使用；RAG 文档放入收件目录不需要它。
- `AGENT_CREDENTIAL_ENCRYPTION_KEY` 应为 Fernet key，可用以下命令生成：

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- 阿里云百炼默认公共兼容地址不需要填写“业务空间 ID”。若账号提供专属工作空间兼容地址，只需把 `AGENT_RAG_EMBEDDING_BASE_URL` 换成该地址。
- 也可以用 `DASHSCOPE_API_KEY` 代替 `AGENT_RAG_EMBEDDING_API_KEY`。
- 若暂不使用 RAG，设置 `AGENT_RAG_ENABLED=false`；Agent 和监控功能仍可运行。
- `LOCAL_CAMERA_SOURCE_TYPE=file` 使用本地视频；`CV_ALLOWED_MEDIA_ROOTS` 必须覆盖视频文件所在目录。

### 3.5 启动

确认 MySQL 已启动、虚拟环境已激活、`.env` 已完成配置后：

```bash
bash scripts/start_stack.sh
```

启动脚本会依次：

1. 执行 `alembic upgrade head`；
2. 启动 Agent API：`http://127.0.0.1:8000`；
3. 启动 Vite 前端：`http://127.0.0.1:5173`；
4. 注册并启动本地 CV 控制节点：`http://127.0.0.1:8100`；
5. 注册 `LOCAL_CAMERA_ID` 并开始监控。

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:5173` | Web 控制台 |
| `http://127.0.0.1:8000/docs` | FastAPI Swagger 接口文档 |
| `http://127.0.0.1:8000/api/v1/cameras/cam_field_01/preview` | 摄像头 MJPEG 实时预览 |
| `http://127.0.0.1:8100/control/v1/health` | CV 控制节点健康检查（需内部令牌） |

日志目录：

```text
runs/logs/agent.log
runs/logs/web.log
runs/logs/cv-control.log
runs/logs/alembic.log
```

`start_stack.sh` 会以前台方式持续运行；在该终端按 `Ctrl+C` 会同时关闭 API、Web 和 CV 控制节点。若进程异常退出，先查看上述日志，再重新执行启动命令。

### 3.6 导入 RAG 文档

RAG 已启用时，直接复制资料：

```bash
mkdir -p runs/knowledge/inbox
cp /path/to/施工安全规范.pdf runs/knowledge/inbox/
```

服务启动后会立即扫描一次，之后按 `AGENT_RAG_SYNC_INTERVAL_SECONDS`（默认 30 秒）扫描；向量和索引数据写入 `runs/chroma/`。保留该目录即可复用已向量化结果；删除它会触发重新建库。

### 3.7 验证与开发检查

```bash
# Agent 测试
python3 -m pytest -q tests/agent

# 前端类型检查与生产构建
cd web && npm run build

# 检查当前迁移版本
cd .. && alembic current
```

## 常见问题

### 启动脚本提示 Agent 未就绪

先查看 `runs/logs/agent.log`。常见原因是 `.env` 的 `AGENT_DATABASE_URL`、`INTERNAL_PERCEPTION_TOKEN`、`AGENT_BIND_HOST`、`AGENT_PORT`、`AGENT_CORS_ORIGINS`、大模型 Key 或 RAG Key 未配置，或 MySQL 尚未启动。启动脚本会自动运行迁移，无需手动创建表。

### 页面显示降级保护模式

这表示 Agent API 或其数据库访问失败。依次检查 `runs/logs/agent.log`、数据库连接、`http://127.0.0.1:8000/docs` 是否可访问，然后刷新浏览器。工具参数错误会作为工具结果回传给模型重试，不应直接触发全局降级。

### RAG 查询不到资料

确认：`AGENT_RAG_ENABLED=true`、DashScope Key 有效、文件在 `runs/knowledge/inbox/`、文件扩展名受 `AGENT_RAG_ALLOWED_EXTENSIONS` 支持，并查看 `runs/logs/agent.log` 中的索引错误。文档原件在 `runs/knowledge/`，向量库在 `runs/chroma/`。

### 违规图片无法预览

确认 `AGENT_MEDIA_ROOT` 与 `CV_SNAPSHOT_DIR` 的映射一致（默认是 `./runs/media` 与 `./runs/media/snapshots`），并确认图片位于 `runs/media/snapshots/`。Agent 会把该目录挂载为 `/media`。

## 相关文档

- [Agent 与 RAG 管理说明](docs/agent/Agent_Memory_RAG_Management.md)
- [CV / Agent / Web 接口契约](docs/integration/CV_Agent_Web_Integration_Contract.md)
- [系统功能与使用指南](docs/migration/SYSTEM_FEATURES_AND_USAGE_GUIDE.md)
