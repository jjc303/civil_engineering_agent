from types import SimpleNamespace

from agent.contracts.chat import ToolResult
from agent.llm.deepseek_adapter import DeepSeekChatModel


class _DecisionClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[object] = []

    def invoke(self, messages: object) -> SimpleNamespace:
        self.calls.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


def _model_with(responses: list[str]) -> tuple[DeepSeekChatModel, _DecisionClient]:
    model = DeepSeekChatModel(api_key="not-used", model_name="test", base_url="https://example.invalid", timeout_seconds=1)
    client = _DecisionClient(responses)
    model._client = client  # type: ignore[assignment]
    return model, client


def test_invalid_tool_plan_is_returned_to_model_for_one_corrective_retry() -> None:
    model, client = _model_with([
        '{"tool_name":"get_workforce_summary"}',
        '{"tool_name":"get_workforce_summary","purpose":"汇总现场作业人数"}',
    ])

    decision = model.decide("查看当前现场作业人数", [], tool_catalog=[{"name": "get_workforce_summary"}])

    assert decision is not None
    assert decision.tool_name == "get_workforce_summary"
    assert len(client.calls) == 2
    retry_text = client.calls[1][1].content  # type: ignore[index,union-attr]
    assert "purpose" in retry_text
    assert "未通过服务端参数校验" in retry_text


def test_model_can_plan_another_bounded_tool_step_after_verified_results() -> None:
    model, client = _model_with([
        '{"tool_name":"query_violations","purpose":"补充最近违规事件"}',
    ])
    previous = [ToolResult(tool_name="get_violation_statistics", data={"total_violations": 2})]

    decision = model.decide("有多少违规，最近一条是什么？", previous, tool_catalog=[{"name": "query_violations"}])

    assert decision is not None
    assert decision.tool_name == "query_violations"
    assert len(client.calls) == 1
    first_step_text = client.calls[0][1].content  # type: ignore[index,union-attr]
    assert "get_violation_statistics" in first_step_text
