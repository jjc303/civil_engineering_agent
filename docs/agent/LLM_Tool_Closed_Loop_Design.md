# Agent LLM—工具最小闭环设计

> **阶段**：Agent 阶段 2（在阶段 1 事件入库闭环之上）  
> **目标**：让 Web 用户能以自然语言询问施工安全状态，由 Agent 安全地选择工具、读取 MySQL 中的业务事实，并输出可追溯的中文结论。  
> **不包含**：向客户端输出模型原始思维链、直接让 LLM 执行 SQL、把 Redis/Chroma 变成主链路依赖。

## 1. 最小闭环的定义

```text
Web 自然语言输入
  ↓ POST /api/v1/agent/chat
API 身份/参数校验
  ↓
LangGraph 编排图
  ├─ 意图与参数抽取（LLM，结构化输出）
  ├─ 工具白名单与参数校验（代码）
  ├─ 安全数据查询（Tool → Repository → MySQL）
  └─ 回答生成（LLM，仅使用已验证工具结果）
  ↓
结构化回答：结论 + 依据 + 工具调用摘要
  ↓
Web 展示
```

一个请求只允许在同一条图路径中进行有限次工具调用（v0.2 默认最多 2 次）。这就是“单主流程”：不是暴露模型内心推理，而是让每一步的输入、输出和转移均可审计。

### 首个可演示问题

> “今天 A01 摄像头有多少严重违规？最近一条是什么？”

Agent 应执行：

1. 解析出时间范围、`camera_id=A01`、`severity=CRITICAL`。
2. 调用违规统计工具；如需“最近一条”，再调用违规列表工具。
3. 依据返回 JSON 生成结论，并返回查询时间范围和事件 UUID。

## 2. 职责边界

| 层 | 责任 | 禁止事项 |
|---|---|---|
| API | 鉴权、请求 ID、限流、DTO 转换、返回响应 | 不解析自然语言、不写 SQL |
| Graph | 状态转移、调用上限、失败分支、审计汇总 | 不依赖某一个模型供应商 |
| LLM Adapter | 调用模型并解析受限结构化输出 | 不持有数据库 Session、不直接执行工具 |
| Tool | 单一业务动作、参数再次校验、返回 JSON | 不接受任意 SQL/文件路径/网络 URL |
| Service / Repository | 业务规则、事务、MySQL 查询 | 不知道提示词、模型或 HTTP |
| Memory / RAG | 后续会话摘要、制度检索 | 不作为事件事实来源 |

**事实来源原则**：违规事件、摄像头状态来自 MySQL；CV 媒体仍以 `snapshot_uri` 关联。LLM 只能解释已取得的事实，不能补造事件、人数或时间。

## 3. 可扩展项目结构

在既有 `agent/` 基础上新增如下模块，旧的事件上报和查询接口保持不变：

```text
agent/
├── api/
│   └── chat.py                     # POST /api/v1/agent/chat
├── contracts/
│   ├── chat.py                     # ChatRequest / ChatResponse / Evidence DTO
│   └── tool_calls.py               # ToolDecision 受限结构化模型
├── graph/
│   ├── state.py                    # ChatGraphState（不含原始 CoT）
│   ├── chat_graph.py               # 图装配入口
│   └── nodes/
│       ├── classify.py              # LLM 结构化意图节点
│       ├── authorize.py             # 白名单、参数、次数校验
│       ├── execute.py               # 统一工具执行节点
│       └── respond.py               # LLM 回答/降级模板节点
├── llm/
│   ├── protocol.py                  # ChatModelPort 抽象
│   ├── langchain_adapter.py         # LangChain ChatModel 适配器
│   └── fake_adapter.py              # 测试用确定性模型
├── tools/
│   ├── registry.py                  # ToolRegistry（已有，扩展元数据）
│   ├── safety_tools.py              # 只读安全业务工具（已有）
│   └── definitions.py               # 参数模型、权限、幂等/只读标记
├── prompts/
│   ├── tool_selection.md            # 工具选择提示词
│   └── response.md                  # 回答约束与证据格式
├── memory/
│   ├── protocol.py                  # ConversationMemoryPort
│   └── redis_adapter.py             # 后续可选实现
└── rag/
    ├── protocol.py                  # KnowledgeRetrieverPort
    └── chroma_adapter.py            # 后续可选实现
```

依赖方向固定为：`api → graph → (llm, tools) → service → repository → db`。`llm`、`memory`、`rag` 只通过 Protocol/Port 被图依赖；因此更换 OpenAI、兼容 API、本地模型，或暂时禁用 Redis/Chroma，都不需要改动事件表和工具实现。

## 4. Graph 状态与节点

### 4.1 状态（可审计，非思维链）

```python
class ChatGraphState(TypedDict):
    request_id: str
    user_id: str | None
    question: str
    conversation_id: str | None
    decision: ToolDecision | None       # 意图、工具名、结构化参数
    tool_results: list[ToolResult]      # 已脱敏 JSON 结果
    evidence: list[Evidence]            # event_uuid / 时间范围 / snapshot_uri
    answer: str | None
    error_code: str | None
```

不保存、返回或记录模型逐字推理文本。审计内容仅含：请求 ID、模型名、选定工具、已校验参数、耗时、成功/失败和证据 ID。

### 4.2 节点与转移

```text
START
  → validate_request
  → load_optional_context
  → select_tool_with_llm
  → validate_tool_decision
  → execute_tool
  → [需要补充事实且次数未超限] select_tool_with_llm
  → generate_answer
  → persist_audit
  → END

任意节点异常 → fallback_response → persist_audit → END
```

`select_tool_with_llm` 必须输出 `ToolDecision` JSON，不允许自由文本充当工具指令：

```json
{
  "tool_name": "query_violations",
  "arguments": {
    "camera_id": "A01",
    "severity": "CRITICAL",
    "start_time_utc": "2026-09-25T00:00:00Z",
    "end_time_utc": "2026-09-25T23:59:59Z",
    "limit": 10
  },
  "purpose": "查询今日严重违规的最近记录"
}
```

代码会以 Pydantic 再次验证 `tool_name`、枚举、时间范围、`limit` 与权限，验证失败则不执行。

## 5. v0.2 必需基础工具

以下 4 个只读工具足以完成比赛期的绝大多数安全问答；前三个基于阶段 1 能力直接封装。

| 工具 | 输入 | 输出 | 数据源 | 用途 |
|---|---|---|---|---|
| `query_violations` | 摄像头、时间、类型、严重级别、状态、分页 | 事件列表与证据 URI | MySQL | 最近事件、筛选明细 |
| `get_violation_statistics` | 摄像头、时间范围 | 总数、分布、平均时长 | MySQL | 今日/本班次统计 |
| `get_camera_status` | `camera_id` | 在线、FPS、帧号、人数、模型版本 | MySQL | 判断设备与感知健康度 |
| `get_safety_rule` | 规则关键词/条款 ID | 制度片段、来源、版本 | Chroma（可选）/本地 fixture | 回答“为什么违规/如何处置” |

### 工具安全约束

1. 每个工具有独立 Pydantic 参数模型，禁止 `dict[str, Any]` 直通。
2. 默认全部只读；任何写操作另建审批型工具，不能复用此注册表权限。
3. 工具名由服务器白名单映射，不能由 LLM 提供 Python 函数名、SQL 或 URL。
4. `query_violations.limit` 上限 100；时间范围默认 24 小时、最大 31 天。
5. 工具结果先转为可序列化 DTO，再传给模型；删除数据库内部字段、令牌和绝对路径。
6. `snapshot_uri` 只作为证据引用，模型不能请求或生成宿主机文件路径。

## 6. API 与响应契约

### 请求

```http
POST /api/v1/agent/chat
Content-Type: application/json

{
  "question": "今天 A01 摄像头有多少严重违规？最近一条是什么？",
  "conversation_id": "optional-web-session-id"
}
```

### 响应

```json
{
  "request_id": "01J...",
  "answer": "今天 A01 摄像头记录到 2 条严重违规；最近一条发生在 14:32，为危险区域入侵。",
  "evidence": [
    {
      "event_uuid": "...",
      "occurred_at_utc": "2026-09-25T14:32:10Z",
      "snapshot_uri": "snapshots/20260925/....jpg"
    }
  ],
  "tool_trace": [
    {"tool_name": "get_violation_statistics", "success": true},
    {"tool_name": "query_violations", "success": true}
  ],
  "degraded": false
}
```

`tool_trace` 是可读审计摘要，不是模型思维链。模型/工具不可用时返回 `degraded=true` 和可行动的说明，例如“统计服务暂不可用，请稍后重试”。

## 7. 分阶段实施与验收

### A. 无模型骨架（先做）

1. 建立 Chat DTO、Graph State、Port 与工具元数据。
2. 使用 `FakeChatModel` 固定返回合法 `ToolDecision`，走完整图。
3. 为输入、工具拒绝、一次/两次工具调用、降级回答编写测试。

**验收**：不配置任何 API Key，固定问题仍可经图、工具、模板回答形成端到端测试。

### B. 接入真实模型

1. 实现 LangChain `ChatModelPort` Adapter，通过环境变量选择供应商、模型名、Base URL。
2. 以 structured output / tool calling 生成 `ToolDecision`。
3. 加入超时、一次重试、调用次数/Token 上限与 JSON 解析失败降级。

**验收**：真实中文提问连续运行，所有工具调用都通过白名单和 Pydantic 校验；无工具请求时不访问数据库。

### C. 可选记忆与 RAG

1. Redis 仅存短期会话摘要和限流计数，失效时退化为无记忆单轮问答。
2. Chroma 仅存安全制度、处置预案、比赛说明等非实时知识；每条检索结果必须带来源和版本。
3. 只有问题涉及“规范/处置/解释”时才调用 `get_safety_rule`。

**验收**：关闭 Redis/Chroma 后，MySQL 事件问答仍可用；RAG 回答能展示知识来源。

## 8. 配置与部署约束

新增环境变量（名称不绑定特定供应商）：

```bash
AGENT_LLM_PROVIDER=openai_compatible
AGENT_LLM_MODEL=<模型名>
AGENT_LLM_BASE_URL=<可选地址>
AGENT_LLM_API_KEY=<密钥>
AGENT_TOOL_MAX_CALLS=2
AGENT_LLM_TIMEOUT_SECONDS=20
```

现有 `AGENT_DATABASE_URL` 和 `INTERNAL_PERCEPTION_TOKEN` 保持不变。密钥只由部署环境注入，绝不写入仓库、提示词、审计记录或 HTTP 响应。

## 9. 开工顺序

1. 先完成 A：接口、端口、假模型、Graph 与测试；这一步不等待 CV。
2. 确认模型供应商、模型名及密钥后完成 B。
3. CV 发布器联调可与 B 并行；LLM 只读阶段 1 已入库的事实。
4. 最后按 Web 需求决定是否启用 Redis/Chroma，不让它们阻塞演示闭环。
