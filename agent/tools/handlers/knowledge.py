from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome, extract_evidence


def _validity_label(validity: str) -> str:
    return {
        "CURRENT": "已确认现行",
        "SUPERSEDED": "已废止或被替代",
        "UNKNOWN": "有效性未确认",
    }.get(validity, "有效性未确认")


def _search_knowledge(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if not ctx.knowledge_service:
        raise RuntimeError("knowledge search is disabled")
    max_top_k = getattr(ctx.knowledge_service, "top_k_max", decision.top_k)
    top_k = min(decision.top_k, max_top_k)
    data, citations = ctx.knowledge_service.search(decision.knowledge_query or "", top_k)
    return ToolOutcome(data=data, evidence=extract_evidence(data), citations=citations)


def _list_standard_catalog(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if not ctx.knowledge_service:
        raise RuntimeError("standards catalog is disabled")
    catalog = ctx.knowledge_service.standard_catalog()
    lines = [
        f"规范目录共 {len(catalog)} 份文件，已完成索引 {sum(status == '已索引' for _, status, _ in catalog)} 份。只有已索引的文件可作为问答依据。",
        "",
    ]
    lines.extend(
        f"{index}. {title}（{status}；{_validity_label(validity)}）"
        for index, (title, status, validity) in enumerate(catalog, 1)
    )
    if not catalog:
        lines.append("当前目录没有可识别的规范文档。")
    return ToolOutcome(data=catalog, answer="\n".join(lines), citations=[])


_REQ_KNOWLEDGE = frozenset({Capability.KNOWLEDGE})

KNOWLEDGE_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="search_knowledge",
        description="按需检索当前有效的事故报告资料；工程规范会自动检索，无需调用此工具。",
        parameters="knowledge_query: string, top_k: integer",
        handler=_search_knowledge,
        requires=_REQ_KNOWLEDGE,
    ),
    AgentTool(
        name="list_standard_catalog",
        description="列出规范目录中的文档及其索引状态、经人工标注的有效性；仅当用户询问库内有哪些规范或标准时使用。",
        parameters="无",
        handler=_list_standard_catalog,
        requires=_REQ_KNOWLEDGE,
    ),
)
