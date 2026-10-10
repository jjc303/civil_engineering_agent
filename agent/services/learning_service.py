from __future__ import annotations

import io
import logging
import os
import re
import secrets
from threading import Lock
from time import monotonic
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from jinja2 import Environment
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from agent.contracts.learning import ReportContent, ReportCreate, ReportResponse, TrainingCreate, TrainingEdit, TrainingQuestion, TrainingResponse, WorkerResult, WorkerSubmit
from agent.db.base import Database
from agent.db.models import KnowledgeDocumentModel, SafetyReportModel, TrainingSubmissionModel, TrainingTaskModel, ViolationEventModel
from agent.llm.protocol import ChatModelPort
from agent.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


class LearningConflictError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _citation(chunk) -> dict:
    return {"document_id": chunk.document_id, "version_no": chunk.version_no, "title": chunk.title, "page_or_section": chunk.page_or_section, "chunk_id": chunk.chunk_id, "document_type": chunk.document_type}


_STANDARD_REFERENCE = re.compile(r"《[^》]{2,100}》|(?:GB/T|GB|JGJ|CJJ|JG/T|DB\d{2}(?:/T)?)\s*\d{2,6}(?:[-.]\d{1,6})?|第[一二三四五六七八九十百千\d]+条|\d+(?:\.\d+)+条", re.IGNORECASE)
_RISK_LABELS = {
    "NO_HELMET": "安全帽未规范佩戴",
    "DANGER_ZONE_INTRUSION": "危险区域进入",
    "DWELL_TIMEOUT": "危险区域停留超时",
}


def _guard_standard_references(texts: list[str], standards: list[str], other_titles: list[str] | None = None) -> None:
    """Reject explicit names/codes/clauses that are absent from supplied evidence."""
    evidence = re.sub(r"\s+", "", "\n".join([*standards, *(other_titles or [])])).casefold()
    for text in texts:
        for match in _STANDARD_REFERENCE.finditer(text):
            reference = match.group()
            if reference.startswith("《") and reference.endswith("》"):
                reference = reference[1:-1]
            if re.sub(r"\s+", "", reference).casefold() not in evidence:
                raise ValueError(f"generated text cites unsupported standard or clause: {match.group()}")


_REPORT_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
@page { size: A4; margin: 21mm 18mm; } body { font-family: 'Noto Sans CJK SC', 'WenQuanYi Zen Hei', sans-serif; color: #263245; font-size: 12px; line-height: 1.7; }
h1 { text-align: center; font-size: 23px; } h2 { margin-top: 20px; border-bottom: 1px solid #cad5e3; font-size: 16px; }
table { width: 100%; border-collapse: collapse; } th, td { border: 1px solid #d8e0e8; padding: 6px; text-align: left; } p { white-space: pre-wrap; }
</style></head><body><h1>施工安全报告</h1><p>统计期间：{{ start }} — {{ end }}</p>
<h2>统计概况</h2><p>有效违规事件：{{ stats.total }}；重复出现次数：{{ stats.repeat_occurrences }}</p>
<p>重复口径：同一摄像头、区域、违规类型在统计期间内再次出现；不代表同一人员重复违规。误报已排除。</p>
<table><tr><th>风险类型</th><th>次数</th></tr>{% for name, count in stats.by_type.items() %}<tr><td>{{ name }}</td><td>{{ count }}</td></tr>{% endfor %}</table>
<h2>总结</h2><p>{{ content.summary }}</p><h2>风险分析</h2><p>{{ content.risk_analysis }}</p><h2>整改建议</h2><p>{{ content.remediation }}</p>
<h2>规范资料</h2>{% if citations %}{% for item in citations %}<p>{{ item.title }} · {{ item.page_or_section }}</p>{% endfor %}{% else %}<p>当前规范库未检索到可引用依据。</p>{% endif %}
</body></html>"""


class LearningService:
    def __init__(self, database: Database, knowledge: KnowledgeService, model: ChatModelPort, report_directory: str, public_base_url: str, display_timezone: str = "Asia/Shanghai", insights_ttl_seconds: int = 600) -> None:
        self.database = database
        self.knowledge = knowledge
        self.model = model
        self.report_directory = Path(report_directory)
        self.public_base_url = public_base_url.rstrip("/")
        self.display_timezone = ZoneInfo(display_timezone)
        self.insights_ttl_seconds = insights_ttl_seconds
        self._insights_lock = Lock()
        self._insights_cache: tuple[tuple, float, dict] | None = None

    def create_report(self, request: ReportCreate) -> ReportResponse:
        with self.database.session() as session:
            conditions = (ViolationEventModel.occurred_at_utc >= request.period_start_utc,
                          ViolationEventModel.occurred_at_utc < request.period_end_utc,
                          ViolationEventModel.status != "FALSE_ALARM")
            total = int(session.scalar(select(func.count()).select_from(ViolationEventModel).where(*conditions)) or 0)
            by_type = dict(session.execute(select(ViolationEventModel.violation_type, func.count()).where(*conditions).group_by(ViolationEventModel.violation_type)).all())
            by_severity = dict(session.execute(select(ViolationEventModel.severity, func.count()).where(*conditions).group_by(ViolationEventModel.severity)).all())
            zones = session.execute(select(ViolationEventModel.zone_name, func.count()).where(*conditions).group_by(ViolationEventModel.zone_name)).all()
            groups = session.execute(select(ViolationEventModel.camera_id, ViolationEventModel.zone_id, ViolationEventModel.violation_type, func.count()).where(*conditions).group_by(ViolationEventModel.camera_id, ViolationEventModel.zone_id, ViolationEventModel.violation_type)).all()
        statistics = {"total": total, "by_type": by_type, "by_severity": by_severity,
                      "by_zone": {name or "未标注区域": count for name, count in zones},
                      "repeat_occurrences": sum(max(0, count - 1) for *_, count in groups),
                      "repeat_groups": sorted(({"camera_id": cam, "zone_id": zone, "violation_type": kind, "count": count} for cam, zone, kind, count in groups if count > 1), key=lambda item: item["count"], reverse=True)[:20],
                      "excluded_status": "FALSE_ALARM", "end_exclusive": True}
        fragments, citations = [], []
        if self.knowledge.rag_manager and by_type:
            fragments, citations = self.knowledge.search_standards("施工安全 " + " ".join(_RISK_LABELS.get(code, code) for code in by_type), min(4, self.knowledge.top_k_max))
        evidence = [{"content": item["content"][:1200], "title": item["title"], "section": item["page_or_section"], "validity_status": item["validity_status"]} for item in fragments]
        instruction = "输出 summary、risk_analysis、remediation 三个非空字符串。用自然中文，不要输出系统枚举代码。所有数量只能来自统计数据，重复出现次数不代表重复违规人数，也不能据此断言管理措施失效。明确说明 data_source；如果是视频回放演示，不得将循环播放产生的告警推断为真实现场风险恶化。引用规范只允许使用给定片段的标题与章节。引用名称和条款编号必须原样摘录，不要改变中文或阿拉伯数字写法；不能确认具体条款时仅引用文档标题和给定页码。有效性为 UNKNOWN 的资料不得称为现行规范；无依据时明确说明。"
        generation_context = {"statistics": statistics, "standards": evidence, "data_source": os.getenv("REPORT_SOURCE_LABEL", "现场监控记录")}
        for attempt in range(2):
            generated = self.model.generate_structured(instruction, generation_context)
            try:
                content = ReportContent.model_validate(generated)
                _guard_standard_references([content.summary, content.risk_analysis, content.remediation], [text for item in evidence for text in (item["title"], item["content"], item["section"])])
                break
            except ValueError as exc:
                if attempt:
                    raise
                generation_context["validation_error"] = str(exc)
                instruction += " 上次输出未通过依据校验，请根据 validation_error 纠正，只使用提供的原文依据。"
        report = SafetyReportModel(report_id=str(uuid4()), period_start_utc=request.period_start_utc, period_end_utc=request.period_end_utc,
                                   status="DRAFT", statistics_json=statistics, citations_json=[item.model_dump(mode="json") for item in citations],
                                   content_json=content.model_dump(), created_at_utc=_now())
        with self.database.session() as session: session.add(report)
        return self._report(report)

    def list_reports(self) -> list[ReportResponse]:
        with self.database.session() as session:
            return [self._report(row) for row in session.scalars(select(SafetyReportModel).order_by(SafetyReportModel.created_at_utc.desc()).limit(100))]

    def current_week_period(self) -> ReportCreate:
        now_local = _now().astimezone(self.display_timezone)
        week_start_local = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return ReportCreate(period_start_utc=week_start_local.astimezone(timezone.utc), period_end_utc=now_local.astimezone(timezone.utc))

    def weekly_overview(self) -> dict:
        period = self.current_week_period()
        week_start, now = period.period_start_utc, period.period_end_utc
        with self.database.session() as session:
            conditions = (ViolationEventModel.occurred_at_utc >= week_start,
                          ViolationEventModel.occurred_at_utc < now,
                          ViolationEventModel.status != "FALSE_ALARM")
            risk_rows = session.execute(select(ViolationEventModel.violation_type, ViolationEventModel.severity, func.count()).where(*conditions).group_by(ViolationEventModel.violation_type, ViolationEventModel.severity)).all()
            total = sum(count for _, _, count in risk_rows)
            critical = sum(count for _, severity, count in risk_rows if severity == "CRITICAL")
            risk_counts: dict[str, int] = {}
            for code, _, count in risk_rows:
                risk_counts[code] = risk_counts.get(code, 0) + count
            weekly_tasks = list(session.scalars(select(TrainingTaskModel).where(TrainingTaskModel.created_at_utc >= week_start, TrainingTaskModel.created_at_utc < now)))
            published_ids = [task.task_id for task in weekly_tasks if task.status == "PUBLISHED"]
            completion_rows = session.execute(select(TrainingSubmissionModel.task_id, func.count(), func.avg(TrainingSubmissionModel.score)).where(TrainingSubmissionModel.task_id.in_(published_ids)).group_by(TrainingSubmissionModel.task_id)).all() if published_ids else []
            completions = {task_id: {"count": count, "average_score": round(float(average or 0), 1)} for task_id, count, average in completion_rows}
        ranked_risks = sorted(risk_counts.items(), key=lambda item: item[1], reverse=True)
        main_risks = [{"code": code, "label": _RISK_LABELS.get(code, code), "count": count} for code, count in ranked_risks[:3]]
        target_count = sum(task.target_count for task in weekly_tasks if task.status == "PUBLISHED")
        completed_count = sum(item["count"] for item in completions.values())
        return {"period_start_utc": week_start.isoformat(), "period_end_utc": now.isoformat(),
                "total_events": total, "high_risk_events": critical, "training_count": len(weekly_tasks),
                "completed_count": completed_count, "target_count": target_count,
                "completion_rate": round(100 * completed_count / target_count, 1) if target_count else 0,
                "main_risks": main_risks,
                "weekly_tasks": [{"task_id": task.task_id, "status": task.status, "completed_count": completions.get(task.task_id, {}).get("count", 0),
                                  "average_score": completions.get(task.task_id, {}).get("average_score", 0),
                                  "target_count": task.target_count} for task in weekly_tasks]}

    def weekly_insights(self, refresh: bool = False) -> dict:
        overview = self.weekly_overview()
        main_risks = overview["main_risks"]
        week_start = datetime.fromisoformat(overview["period_start_utc"])
        key = (overview["period_start_utc"], tuple(risk["code"] for risk in main_risks))
        with self._insights_lock:
            cached = self._insights_cache
            if not refresh and cached and cached[0] == key and cached[1] > monotonic():
                return cached[2]
            result = self._generate_weekly_insights(main_risks, week_start)
            ttl_seconds = self.insights_ttl_seconds if result["advice"] or not main_risks else min(60, self.insights_ttl_seconds)
            self._insights_cache = (key, monotonic() + ttl_seconds, result)
            return result

    def _generate_weekly_insights(self, main_risks: list[dict], week_start: datetime) -> dict:
        recommendation_scores: dict[str, float] = {}
        recommendation_risks: dict[str, set[str]] = {}
        if self.knowledge.rag_manager:
            for risk in main_risks:
                try:
                    _, citations = self.knowledge.search(f"施工安全事故 {risk['label']}", min(8, self.knowledge.top_k_max))
                except Exception:
                    logger.exception("Could not retrieve accident cases for weekly risk")
                    continue
                for citation in citations:
                    recommendation_scores[citation.document_id] = recommendation_scores.get(citation.document_id, 0.0) + max(0.0, citation.relevance_score) * risk["count"]
                    recommendation_risks.setdefault(citation.document_id, set()).add(risk["label"])
        ranked_ids = sorted(recommendation_scores, key=recommendation_scores.get, reverse=True)[:4]
        with self.database.session() as session:
            recommended_rows = {row.document_id: row for row in session.scalars(select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.document_id.in_(ranked_ids), KnowledgeDocumentModel.status == "ACTIVE", KnowledgeDocumentModel.document_type == "ACCIDENT_REPORT"))} if ranked_ids else {}
        recommendations = [{**self.knowledge._document(recommended_rows[document_id]).model_dump(mode="json"),
                            "related_risks": sorted(recommendation_risks[document_id]),
                            "relevance_score": round(recommendation_scores[document_id], 3)}
                           for document_id in ranked_ids if document_id in recommended_rows]
        advice = ""
        if main_risks:
            try:
                standards, _ = self.knowledge.search_standards(" ".join(risk["label"] for risk in main_risks), min(3, self.knowledge.top_k_max)) if self.knowledge.rag_manager else ([], [])
                payload = self.model.generate_structured(
                    "根据本周风险和给定案例、规范片段，输出 advice 字符串：给管理者两到三条具体、可执行的安全教育建议。优先说明应培训的操作和检查动作；不得写具体事件次数、人数，不得虚构人员重复违规、事故经过或规范条款。若资料不足，应明确指出可核对的范围。",
                    {"period_start": week_start.astimezone(self.display_timezone).date().isoformat(),
                     "risks": [{"code": risk["code"], "label": risk["label"]} for risk in main_risks],
                     "cases": [{"title": row["title"], "summary": row["summary"]} for row in recommendations[:3]],
                     "standards": [{"title": item["title"], "section": item["page_or_section"], "content": item["content"][:600]} for item in standards]})
                advice = str(payload.get("advice", "")).strip()
            except Exception:
                logger.exception("Could not generate weekly education advice")
        return {"period_start_utc": week_start.isoformat(), "risk_codes": [risk["code"] for risk in main_risks],
                "recommended_cases": recommendations, "advice": advice, "generated_at_utc": _now().isoformat()}

    def get_report(self, report_id: str) -> ReportResponse:
        with self.database.session() as session:
            row = session.get(SafetyReportModel, report_id)
            if not row: raise KeyError("report not found")
            return self._report(row)

    def delete_report(self, report_id: str) -> None:
        pdf_path: Path | None = None
        with self.database.session() as session:
            row = session.get(SafetyReportModel, report_id)
            if not row: raise KeyError("report not found")
            if session.scalar(select(TrainingTaskModel.task_id).where(TrainingTaskModel.report_id == report_id).limit(1)):
                raise LearningConflictError("请先删除关联的培训任务，再删除报告")
            if row.pdf_path:
                pdf_path = self.report_directory / f"{row.report_id}.pdf"
            session.delete(row)
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove deleted report PDF: %s", pdf_path, exc_info=True)

    def edit_report(self, report_id: str, content: ReportContent) -> ReportResponse:
        with self.database.session() as session:
            row = session.get(SafetyReportModel, report_id)
            if not row: raise KeyError("report not found")
            if row.status != "DRAFT": raise ValueError("confirmed report cannot be edited")
            row.content_json = content.model_dump()
            session.flush()
            return self._report(row)

    def confirm_report(self, report_id: str) -> ReportResponse:
        with self.database.session() as session:
            row = session.get(SafetyReportModel, report_id)
            if not row: raise KeyError("report not found")
            if row.status != "DRAFT": raise ValueError("report is already confirmed")
            path = self.report_directory / f"{row.report_id}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            start = row.period_start_utc.replace(tzinfo=timezone.utc) if row.period_start_utc.tzinfo is None else row.period_start_utc
            end = row.period_end_utc.replace(tzinfo=timezone.utc) if row.period_end_utc.tzinfo is None else row.period_end_utc
            html = Environment(autoescape=True).from_string(_REPORT_HTML).render(
                start=start.astimezone(self.display_timezone).date(), end=(end - timedelta(microseconds=1)).astimezone(self.display_timezone).date(), stats=row.statistics_json,
                content=row.content_json, citations=row.citations_json)
            if os.name == "nt":
                from agent.services.report_pdf import write_windows_report
                write_windows_report(path,
                    start=str(start.astimezone(self.display_timezone)),
                    end=str(end.astimezone(self.display_timezone)),
                    stats=row.statistics_json, content=row.content_json, citations=row.citations_json or [])
            else:
                from weasyprint import HTML
                HTML(string=html).write_pdf(str(path))
            row.pdf_path = f"{row.report_id}.pdf"
            row.status, row.confirmed_at_utc = "CONFIRMED", _now()
            session.flush()
            return self._report(row)

    def pdf_path(self, report_id: str) -> Path:
        with self.database.session() as session:
            row = session.get(SafetyReportModel, report_id)
            if not row or row.status != "CONFIRMED" or not row.pdf_path:
                raise KeyError("confirmed report PDF not found")
            path = self.report_directory / f"{row.report_id}.pdf"
            if not path.is_file(): raise KeyError("confirmed report PDF not found")
            return path

    @staticmethod
    def _report(row: SafetyReportModel) -> ReportResponse:
        return ReportResponse(report_id=row.report_id, period_start_utc=row.period_start_utc, period_end_utc=row.period_end_utc,
                              status=row.status, statistics=row.statistics_json, citations=row.citations_json or [],
                              content=ReportContent.model_validate(row.content_json), pdf_url=f"/api/v1/learning/reports/{row.report_id}/pdf" if row.pdf_path else None,
                              created_at_utc=row.created_at_utc)

    def search_documents(self, query: str, risk_type: str | None, document_type: str | None, limit: int, offset: int, date_start: datetime | None = None, date_end: datetime | None = None) -> dict:
        with self.database.session() as session:
            stmt = select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.status == "ACTIVE")
            if document_type: stmt = stmt.where(KnowledgeDocumentModel.document_type == document_type)
            if date_start: stmt = stmt.where(KnowledgeDocumentModel.document_date >= date_start)
            if date_end: stmt = stmt.where(KnowledgeDocumentModel.document_date < date_end)
            rows = list(session.scalars(stmt.order_by(KnowledgeDocumentModel.created_at_utc.desc())))
        rows = [row for row in rows if row.document_type != "STANDARD" or row.validity_status != "SUPERSEDED"]
        if risk_type: rows = [row for row in rows if risk_type in (row.risk_tags or [])]
        scores: dict[str, float] = {}
        if query.strip() and self.knowledge.rag_manager:
            for kind in ([document_type] if document_type else ["ACCIDENT_REPORT", "STANDARD"]):
                _, hits = self.knowledge._search_type(kind, query.strip(), self.knowledge.top_k_max)
                for hit in hits: scores[hit.document_id] = max(scores.get(hit.document_id, 0), hit.relevance_score)
        if query.strip():
            term = query.strip().casefold()
            rows = [row for row in rows if term in row.title.casefold() or term in (row.summary or "").casefold() or row.document_id in scores]
            rows.sort(key=lambda row: (scores.get(row.document_id, 0), row.created_at_utc), reverse=True)
        total = len(rows)
        return {"items": [{**self.knowledge._document(row).model_dump(mode="json"), "relevance_score": scores.get(row.document_id)} for row in rows[offset:offset + limit]], "total": total, "limit": limit, "offset": offset}

    def case_detail(self, document_id: str) -> dict:
        detail = self.knowledge.detail(document_id)
        if detail.document_type != "ACCIDENT_REPORT": raise ValueError("document is not an accident report")
        chunks = self.knowledge.document_chunks(document_id)
        if not chunks: raise ValueError("document has no indexed content")
        selected = chunks[:30]
        standard_fragments, standard_citations = (self.knowledge.search_standards(" ".join([detail.title, *detail.risk_tags]), min(4, self.knowledge.top_k_max)) if self.knowledge.rag_manager else ([], []))
        payload = self.model.generate_structured("根据事故报告原文输出 process、causes、risks、prevention 四个字符串。事故经过与原因只能来自事故报告；防范措施可参考给定规范。有效性为 UNKNOWN 的规范不得称为现行规范；不明事实写明原文未说明。", {"title": detail.title, "accident_chunks": [{"text": c.text, "section": c.page_or_section} for c in selected], "standards": standard_fragments})
        _guard_standard_references([str(payload.get(key, "")) for key in ("process", "causes", "risks", "prevention")], [text for item in standard_fragments for text in (item["title"], item["content"], item["page_or_section"])], [detail.title])
        return {"document_id": document_id, "title": detail.title, **{key: str(payload.get(key, "原文未说明。")) for key in ("process", "causes", "risks", "prevention")}, "citations": [_citation(c) for c in selected] + [item.model_dump(mode="json") for item in standard_citations]}

    def document_fragments(self, document_id: str) -> dict:
        detail = self.knowledge.detail(document_id)
        chunks = self.knowledge.document_chunks(document_id)
        return {"document_id": document_id, "title": detail.title,
                "items": [{"content": chunk.text, "citation": _citation(chunk)} for chunk in chunks[:30]]}

    def create_training(self, request: TrainingCreate) -> TrainingResponse:
        with self.database.session() as session:
            report = session.get(SafetyReportModel, request.report_id)
            if not report or report.status != "CONFIRMED": raise ValueError("training requires a confirmed report")
            report_snapshot = {"statistics": report.statistics_json, "content": report.content_json}
        selected = []
        for document_id in dict.fromkeys(request.document_ids):
            detail = self.knowledge.detail(document_id)
            chunks = self.knowledge.document_chunks(document_id)
            selected.append({"document_id": document_id, "title": detail.title, "document_type": detail.document_type,
                             "version_no": detail.current_version, "validity_status": detail.validity_status,
                             "chunks": [{"content": c.text, "section": c.page_or_section, "chunk_id": c.chunk_id} for c in chunks[:6]]})
        if self.knowledge.rag_manager:
            standard_fragments, standard_citations = self.knowledge.search_standards("施工安全 " + " ".join(_RISK_LABELS.get(code, code) for code in report_snapshot["statistics"]["by_type"]), min(4, self.knowledge.top_k_max))
            selected_ids = {doc["document_id"] for doc in selected}
            for fragment, citation in zip(standard_fragments, standard_citations):
                if citation.document_id in selected_ids: continue
                selected.append({"document_id": citation.document_id, "title": citation.title, "document_type": "STANDARD", "version_no": citation.version_no,
                                 "validity_status": fragment["validity_status"], "auto_retrieved": True,
                                 "chunks": [{"content": fragment["content"], "section": citation.page_or_section, "chunk_id": citation.chunk_id}]})
                selected_ids.add(citation.document_id)
        report_content = report_snapshot["content"]
        generation_context = {"report": report_content, "documents": selected, "question_count": request.question_count}
        instruction = (
            "你是面向施工现场作业人员的安全培训出题人。仅输出 JSON 对象，含 material 字符串与 questions 数组。"
            f"恰好生成 {request.question_count} 道互不重复的四选一单选题，每题含 stem、options（恰好四个非空且不同的选项）、answer（0—3 的正确选项索引）、evidence（从所给报告文字或文档片段摘录的出题依据）。"
            "学习材料和题目只依据报告的风险分析、整改建议及给定事故案例和规范原文；优先从事故案例和规范原文提取考点。报告统计次数仅用于确定培训重点，禁止考查次数、人数、比例或表格数字。"
            "每题设置一个具体施工情境，考查风险识别、正确处置、预防措施或事故教训；正确答案应能从 evidence 直接推得，另外三个选项应是现场可能出现但不正确的做法。"
            "用自然、专业的中文表述，禁止出现 NO_HELMET、CRITICAL 等系统枚举代码，禁止只换数字或选项顺序重复出题。"
            "不要编造事故事实、规范名称或条款；有效性 UNKNOWN 的规范不能称为现行。若资料不足以支撑指定题数，应说明依据不足，不要凑题。"
        )
        generated = self.model.generate_structured(instruction, generation_context)
        material = str(generated.get("material", "")).strip()
        questions = [TrainingQuestion.model_validate(item) for item in generated.get("questions", [])]
        if not material or len(questions) != request.question_count:
            raise ValueError("培训内容或题目数量不完整，请补充案例、规范资料或减少题数")
        row = TrainingTaskModel(task_id=str(uuid4()), report_id=request.report_id, status="DRAFT", title=request.title,
                                target_count=request.target_count, question_count=request.question_count, pass_score=request.pass_score,
                                selected_documents_json=selected, material=material, questions_json=[q.model_dump() for q in questions], created_at_utc=_now())
        with self.database.session() as session: session.add(row)
        return self._task(row)

    def list_training(self) -> list[TrainingResponse]:
        with self.database.session() as session:
            return [self._task(row) for row in session.scalars(select(TrainingTaskModel).order_by(TrainingTaskModel.created_at_utc.desc()).limit(100))]

    def get_training(self, task_id: str) -> TrainingResponse:
        with self.database.session() as session:
            row = session.get(TrainingTaskModel, task_id)
            if not row: raise KeyError("training task not found")
            return self._task(row)

    def delete_training(self, task_id: str) -> None:
        with self.database.session() as session:
            row = session.get(TrainingTaskModel, task_id)
            if not row: raise KeyError("training task not found")
            session.execute(delete(TrainingSubmissionModel).where(TrainingSubmissionModel.task_id == task_id))
            session.delete(row)

    def edit_training(self, task_id: str, request: TrainingEdit) -> TrainingResponse:
        with self.database.session() as session:
            row = session.get(TrainingTaskModel, task_id)
            if not row: raise KeyError("training task not found")
            if row.status != "DRAFT": raise ValueError("published training cannot be edited")
            row.title, row.target_count, row.pass_score, row.material = request.title, request.target_count, request.pass_score, request.material
            row.question_count = len(request.questions)
            row.questions_json = [q.model_dump() for q in request.questions]
            session.flush()
            return self._task(row)

    def publish_training(self, task_id: str) -> TrainingResponse:
        if not self.public_base_url: raise ValueError("LEARNING_PUBLIC_BASE_URL must be configured")
        with self.database.session() as session:
            row = session.get(TrainingTaskModel, task_id)
            if not row: raise KeyError("training task not found")
            if row.status != "DRAFT": raise ValueError("training task is already published")
            row.access_token = secrets.token_urlsafe(24)
            row.status, row.published_at_utc = "PUBLISHED", _now()
            session.flush()
            return self._task(row)

    def _task(self, row: TrainingTaskModel) -> TrainingResponse:
        url = f"{self.public_base_url}/learn/{row.access_token}" if row.access_token and self.public_base_url else None
        return TrainingResponse(task_id=row.task_id, report_id=row.report_id, status=row.status, title=row.title,
                                target_count=row.target_count, question_count=row.question_count, pass_score=row.pass_score,
                                selected_documents=[{key: doc[key] for key in ("document_id", "title", "document_type", "version_no", "validity_status")} for doc in (row.selected_documents_json or [])], material=row.material,
                                questions=[TrainingQuestion.model_validate(q) for q in row.questions_json], public_url=url,
                                qr_url=f"/api/v1/learning/training/{row.task_id}/qr" if url else None)

    def qr_png(self, task_id: str) -> bytes:
        import qrcode
        task = self.get_training(task_id)
        if not task.public_url: raise ValueError("training task is not published")
        output = io.BytesIO()
        qrcode.make(task.public_url).save(output, format="PNG")
        return output.getvalue()

    def public_task(self, token: str) -> dict:
        with self.database.session() as session:
            row = session.scalar(select(TrainingTaskModel).where(TrainingTaskModel.access_token == token, TrainingTaskModel.status == "PUBLISHED"))
            if not row: raise KeyError("training task not found")
            return {"title": row.title, "material": row.material, "questions": [{"stem": q["stem"], "options": q["options"]} for q in row.questions_json], "question_count": row.question_count}

    def submit(self, token: str, payload: WorkerSubmit) -> WorkerResult:
        worker_id, worker_name = payload.worker_id.strip(), payload.worker_name.strip()
        if not worker_id or not worker_name: raise ValueError("worker ID and name are required")
        try:
            with self.database.session() as session:
                row = session.scalar(select(TrainingTaskModel).where(TrainingTaskModel.access_token == token, TrainingTaskModel.status == "PUBLISHED"))
                if not row: raise KeyError("training task not found")
                if len(payload.answers) != len(row.questions_json) or any(a < 0 or a >= len(q["options"]) for a, q in zip(payload.answers, row.questions_json)):
                    raise ValueError("answers do not match the published questions")
                if session.scalar(select(TrainingSubmissionModel.submission_id).where(TrainingSubmissionModel.task_id == row.task_id, TrainingSubmissionModel.worker_id == worker_id)):
                    raise RuntimeError("worker has already submitted this task")
                correct = sum(answer == question["answer"] for answer, question in zip(payload.answers, row.questions_json))
                score = round(100 * correct / len(row.questions_json))
                passed = score >= row.pass_score
                session.add(TrainingSubmissionModel(submission_id=str(uuid4()), task_id=row.task_id, worker_id=worker_id, worker_name=worker_name,
                                                    answers_json=payload.answers, score=score, passed=passed, submitted_at_utc=_now()))
            return WorkerResult(score=score, passed=passed)
        except IntegrityError as exc:
            raise RuntimeError("worker has already submitted this task") from exc

    def training_statistics(self, task_id: str) -> dict:
        with self.database.session() as session:
            task = session.get(TrainingTaskModel, task_id)
            if not task: raise KeyError("training task not found")
            submissions = list(session.scalars(select(TrainingSubmissionModel).where(TrainingSubmissionModel.task_id == task_id).order_by(TrainingSubmissionModel.submitted_at_utc.desc())))
            completed = len(submissions)
            return {"target_count": task.target_count, "completed_count": completed,
                    "completion_rate": round(100 * completed / task.target_count, 1),
                    "average_score": round(sum(item.score for item in submissions) / completed, 1) if completed else 0,
                    "pass_rate": round(100 * sum(item.passed for item in submissions) / completed, 1) if completed else 0,
                    "submissions": [{"worker_id": item.worker_id, "worker_name": item.worker_name, "score": item.score, "passed": item.passed, "submitted_at_utc": _as_utc(item.submitted_at_utc).isoformat()} for item in submissions]}
