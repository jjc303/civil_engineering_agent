# DeepSeek 接入说明

## 已实现的接入方式

Agent 通过 LangChain `ChatOpenAI` 使用 DeepSeek 的 OpenAI 兼容接口。模型适配器只实现 `ChatModelPort`，不持有数据库会话；工具白名单、参数校验、调用上限和 MySQL 访问仍由 LangGraph 与应用层控制。

工具决策阶段强制请求 JSON 对象，并由服务端再次解析为 `ToolDecision`。回答阶段只接收已验证的工具结果。模型的原始 reasoning/thinking 内容不会写入审计、数据库或 API 响应。

## 配置

在部署环境中注入以下变量，密钥不要提交到 Git：

```bash
# 可省略；DeepSeek 是默认提供方。
export AGENT_LLM_PROVIDER='deepseek'
export AGENT_LLM_MODEL='deepseek-flash'
export AGENT_LLM_BASE_URL='https://api.deepseek.com'
export AGENT_LLM_API_KEY='你的 DeepSeek API Key'
export AGENT_LLM_TIMEOUT_SECONDS='20'
export AGENT_TOOL_MAX_CALLS='2'
```

然后启动：

```bash
python3 -m uvicorn agent.main:create_app --factory --host 0.0.0.0 --port 8000
```

未设置 `AGENT_LLM_PROVIDER` 时使用 `deepseek`。因此正常启动必须提供 `AGENT_LLM_API_KEY`；未提供 Key 时服务会拒绝启动。离线开发和 CI 请显式设置 `AGENT_LLM_PROVIDER=fake`，不会访问外部模型。

## 请求示例

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/agent/chat' \
  -H 'Content-Type: application/json' \
  -d '{"question":"A01 摄像头今天有多少严重违规？最近一条是什么？"}'
```

接口返回 `answer`、可展示的 `evidence`、不包含推理文本的 `tool_trace`，以及发生模型或工具故障时的 `degraded` 标记。

## 模型选择

比赛演示默认建议使用 `deepseek-flash`，以较低延迟处理“查询/统计/状态”类问题。需要更强复杂推理时，可将 `AGENT_LLM_MODEL` 改为 `deepseek-v4-pro`，其余代码不变。

## 尚待执行的真实联调

适配器构造、结构化输出路径和全量本地测试已覆盖，但尚未使用真实 API Key 发送请求。提供 Key 后，应在有真实 CV 事件的 MySQL 库中验证：

1. 中文问题能得到合法工具选择 JSON；
2. 工具结果与 MySQL 查询结果一致；
3. 回答中的事件 UUID、时间和截图 URI 都可追溯；
4. API Key、数据库密码和模型 reasoning 均不出现在响应或日志中。
