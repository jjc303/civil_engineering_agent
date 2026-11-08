from __future__ import annotations

import io
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from agent.contracts.learning import (
    ReportContent,
    ReportCreate,
    ReportResponse,
    TrainingCreate,
    TrainingEdit,
    TrainingQuestion,
    TrainingResponse,
    WorkerResult,
    WorkerSubmit,
)
from agent.db.base import Database
from agent.db.models import SafetyReportModel, TrainingSubmissionModel, TrainingTaskModel
from agent.domain.standards_guard import guard_standard_references as _guard_standard_references
from agent.domain.violation_catalog import VIOLATION_RETRIEVAL_TERMS
from agent.llm.protocol import ChatModelPort
from agent.prompts import load_prompt
from agent.repositories.learning import LearningRepository
from agent.services.knowledge_service import KnowledgeService
from agent.services.report_pdf import render_safety_report_pdf
from agent.services.training_qr import (
    build_training_public_url,
    build_training_qr_url,
    generate_training_qr_png,
)

logger = logging.getLogger(__name__)


class LearningConflictError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _citation(chunk) -> dict:
    return {
        "document_id": chunk.document_id,
        "version_no": chunk.version_no,
        "title": chunk.title,
        "page_or_section": chunk.page_or_section,
        "chunk_id": chunk.chunk_id,
        "document_type": chunk.document_type,
    }


_RISK_LABELS = VIOLATION_RETRIEVAL_TERMS


class LearningService:
    def __init__(
        self,
        database: Database,
        knowledge: KnowledgeService,
        model: ChatModelPort,
        report_directory: str,
        public_base_url: str,
        display_timezone: str = "Asia/Shanghai",
        insights_ttl_seconds: int = 600,
        app_base_path: str = "",
        notification_service: Any = None,
        report_source_label: str | None = None,
        cache: Any | None = None,
    ) -> None:
        self.database = database
        self.knowledge = knowledge
        self.model = model
        self.report_directory = Path(report_directory)
        self.public_base_url = public_base_url.rstrip("/")
        self.app_base_path = app_base_path.rstrip("/")
        self.display_timezone = ZoneInfo(display_timezone)
        self.insights_ttl_seconds = insights_ttl_seconds
        self.notification_service = notification_service
        self.report_source_label = report_source_label
        self.cache = cache
        self._insights_lock = Lock()
        self._insights_cache: tuple[tuple, float, dict] | None = None

    def create_report(self, request: ReportCreate) -> ReportResponse:
        with self.database.session() as session:
            repo = LearningRepository(session)
            statistics = repo.aggregate_period_violations(
                request.period_start_utc,
                request.period_end_utc,
            )
        by_type = statistics["by_type"]
        fragments, citations = [], []
        if self.knowledge.rag_manager and by_type:
            fragments, citations = self.knowledge.search_standards(
                "施工安全 " + " ".join(_RISK_LABELS.get(code, code) for code in by_type),
                min(4, self.knowledge.top_k_max),
            )
        evidence = [
            {
                "content": item["content"][:1200],
                "title": item["title"],
                "section": item["page_or_section"],
                "validity_status": item["validity_status"],
            }
            for item in fragments
        ]
        instruction = load_prompt("report_generation")
        source_label = self.report_source_label or os.getenv("REPORT_SOURCE_LABEL", "现场监控记录")
        generation_context = {"statistics": statistics, "standards": evidence, "data_source": source_label}
        for attempt in range(2):
            generated = self.model.generate_structured(instruction, generation_context)
            try:
                content = ReportContent.model_validate(generated)
                _guard_standard_references(
                    [content.summary, content.risk_analysis, content.remediation],
                    [text for item in evidence for text in (item["title"], item["content"], item["section"])],
                )
                break
            except ValueError as exc:
                if attempt:
                    raise
                generation_context["validation_error"] = str(exc)
                instruction += " 上次输出未通过依据校验，请根据 validation_error 纠正，只使用提供的原文依据。"
        report = SafetyReportModel(
            report_id=str(uuid4()),
            period_start_utc=request.period_start_utc,
            period_end_utc=request.period_end_utc,
            status="DRAFT",
            statistics_json=statistics,
            citations_json=[item.model_dump(mode="json") for item in citations],
            content_json=content.model_dump(),
            created_at_utc=_now(),
        )
        with self.database.session() as session:
            LearningRepository(session).add_report(report)
        return self._report(report)

    def list_reports(self) -> list[ReportResponse]:
        with self.database.session() as session:
            return [self._report(row) for row in LearningRepository(session).list_reports(limit=100)]

    def current_week_period(self) -> ReportCreate:
        now_local = _now().astimezone(self.display_timezone)
        week_start_local = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return ReportCreate(period_start_utc=week_start_local.astimezone(timezone.utc), period_end_utc=now_local.astimezone(timezone.utc))

    def weekly_overview(self) -> dict:
        period = self.current_week_period()
        week_start, now = period.period_start_utc, period.period_end_utc
        with self.database.session() as session:
            risk_rows, weekly_tasks, completions = LearningRepository(session).aggregate_weekly_overview(week_start, now)
        total = sum(count for _, _, count in risk_rows)
        critical = sum(count for _, severity, count in risk_rows if severity == "CRITICAL")
        risk_counts: dict[str, int] = {}
        for code, _, count in risk_rows:
            risk_counts[code] = risk_counts.get(code, 0) + count
        ranked_risks = sorted(risk_counts.items(), key=lambda item: item[1], reverse=True)
        main_risks = [{"code": code, "label": _RISK_LABELS.get(code, code), "count": count} for code, count in ranked_risks[:3]]
        target_count = sum(task.target_count for task in weekly_tasks if task.status == "PUBLISHED")
        completed_count = sum(item["count"] for item in completions.values())
        covered_count = sum(
            min(task.target_count, completions.get(task.task_id, {}).get("count", 0))
            for task in weekly_tasks
            if task.status == "PUBLISHED"
        )
        return {
            "period_start_utc": week_start.isoformat(),
            "period_end_utc": now.isoformat(),
            "total_events": total,
            "high_risk_events": critical,
            "training_count": len(weekly_tasks),
            "completed_count": completed_count,
            "target_count": target_count,
            "completion_rate": round(100 * covered_count / target_count, 1) if target_count else 0,
            "excess_completed_count": completed_count - covered_count,
            "main_risks": main_risks,
            "weekly_tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "completed_count": completions.get(task.task_id, {}).get("count", 0),
                    "average_score": completions.get(task.task_id, {}).get("average_score", 0),
                    "target_count": task.target_count,
                }
                for task in weekly_tasks
            ],
        }

    def weekly_insights(self, refresh: bool = False) -> dict:
        overview = self.weekly_overview()
        main_risks = overview["main_risks"]
        week_start = datetime.fromisoformat(overview["period_start_utc"])
        risk_codes = tuple(sorted(risk["code"] for risk in main_risks))
        key = (overview["period_start_utc"], risk_codes)
        cache_key = f"insights:{overview['period_start_utc']}:{','.join(risk_codes)}"

        if not refresh and self.cache is not None:
            cached_val = self.cache.get_json("learning", cache_key)
            if cached_val is not None:
                return cached_val

        with self._insights_lock:
            cached = self._insights_cache
            if not refresh and cached and cached[0] == key and cached[1] > monotonic():
                return cached[2]
            result = self._generate_weekly_insights(main_risks, week_start)
            ttl_seconds = self.insights_ttl_seconds if result["advice"] or not main_risks else min(60, self.insights_ttl_seconds)
            self._insights_cache = (key, monotonic() + ttl_seconds, result)
            if self.cache is not None:
                self.cache.set_json("learning", cache_key, result, ttl_seconds=ttl_seconds)
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
            recommended_rows = LearningRepository(session).get_active_accident_reports_by_ids(ranked_ids)
        recommendations = [
            {
                **self.knowledge._document(recommended_rows[document_id]).model_dump(mode="json"),
                "related_risks": sorted(recommendation_risks[document_id]),
                "relevance_score": round(recommendation_scores[document_id], 3),
            }
            for document_id in ranked_ids
            if document_id in recommended_rows
        ]
        advice = ""
        if main_risks:
            try:
                standards, _ = (
                    self.knowledge.search_standards(
                        " ".join(risk["label"] for risk in main_risks),
                        min(3, self.knowledge.top_k_max),
                    )
                    if self.knowledge.rag_manager
                    else ([], [])
                )
                payload = self.model.generate_structured(
                    load_prompt("weekly_advice"),
                    {
                        "period_start": week_start.astimezone(self.display_timezone).date().isoformat(),
                        "risks": [{"code": risk["code"], "label": risk["label"]} for risk in main_risks],
                        "cases": [{"title": row["title"], "summary": row["summary"]} for row in recommendations[:3]],
                        "standards": [{"title": item["title"], "section": item["page_or_section"], "content": item["content"][:600]} for item in standards],
                    },
                )
                advice = str(payload.get("advice", "")).strip()
            except Exception:
                logger.exception("Could not generate weekly education advice")
        return {
            "period_start_utc": week_start.isoformat(),
            "risk_codes": [risk["code"] for risk in main_risks],
            "recommended_cases": recommendations,
            "advice": advice,
            "generated_at_utc": _now().isoformat(),
        }

    def get_report(self, report_id: str) -> ReportResponse:
        with self.database.session() as session:
            row = LearningRepository(session).get_report(report_id)
            if not row:
                raise KeyError("report not found")
            return self._report(row)

    def delete_report(self, report_id: str) -> None:
        pdf_path: Path | None = None
        with self.database.session() as session:
            repo = LearningRepository(session)
            row = repo.get_report(report_id)
            if not row:
                raise KeyError("report not found")
            if repo.has_training_for_report(report_id):
                raise LearningConflictError("请先删除关联的培训任务，再删除报告")
            if row.pdf_path:
                pdf_path = self.report_directory / f"{row.report_id}.pdf"
            repo.delete_report(row)
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove deleted report PDF: %s", pdf_path, exc_info=True)

    def edit_report(self, report_id: str, content: ReportContent) -> ReportResponse:
        with self.database.session() as session:
            row = LearningRepository(session).get_report(report_id)
            if not row:
                raise KeyError("report not found")
            if row.status != "DRAFT":
                raise ValueError("confirmed report cannot be edited")
            row.content_json = content.model_dump()
            session.flush()
            return self._report(row)

    def confirm_report(self, report_id: str) -> ReportResponse:
        with self.database.session() as session:
            row = LearningRepository(session).get_report(report_id)
            if not row:
                raise KeyError("report not found")
            if row.status != "DRAFT":
                raise ValueError("report is already confirmed")
            path = self.report_directory / f"{row.report_id}.pdf"
            render_safety_report_pdf(
                path,
                period_start_utc=row.period_start_utc,
                period_end_utc=row.period_end_utc,
                display_timezone=self.display_timezone,
                stats=row.statistics_json,
                content=row.content_json,
                citations=row.citations_json,
                source_label=self.report_source_label,
            )
            row.pdf_path = f"{row.report_id}.pdf"
            row.status, row.confirmed_at_utc = "CONFIRMED", _now()
            session.flush()
            report = self._report(row)
        if self.notification_service is not None:
            self.notification_service.notify_report_confirmed(report)
        return report

    def pdf_path(self, report_id: str) -> Path:
        with self.database.session() as session:
            row = LearningRepository(session).get_report(report_id)
            if not row or row.status != "CONFIRMED" or not row.pdf_path:
                raise KeyError("confirmed report PDF not found")
            path = self.report_directory / f"{row.report_id}.pdf"
            if not path.is_file():
                raise KeyError("confirmed report PDF not found")
            return path

    def _report(self, row: SafetyReportModel) -> ReportResponse:
        return ReportResponse(
            report_id=row.report_id,
            period_start_utc=row.period_start_utc,
            period_end_utc=row.period_end_utc,
            status=row.status,
            statistics=row.statistics_json,
            citations=row.citations_json or [],
            content=ReportContent.model_validate(row.content_json),
            pdf_url=f"{self.app_base_path}/api/v1/learning/reports/{row.report_id}/pdf" if row.pdf_path else None,
            created_at_utc=row.created_at_utc,
        )

    def search_documents(
        self,
        query: str,
        risk_type: str | None,
        document_type: str | None,
        limit: int,
        offset: int,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> dict:
        with self.database.session() as session:
            rows = LearningRepository(session).query_active_documents(
                document_type=document_type,
                date_start=date_start,
                date_end=date_end,
            )
        rows = [row for row in rows if row.document_type != "STANDARD" or row.validity_status != "SUPERSEDED"]
        if risk_type:
            rows = [row for row in rows if risk_type in (row.risk_tags or [])]
        scores: dict[str, float] = {}
        if query.strip() and self.knowledge.rag_manager:
            for kind in ([document_type] if document_type else ["ACCIDENT_REPORT", "STANDARD"]):
                _, hits = self.knowledge._search_type(kind, query.strip(), self.knowledge.top_k_max)
                for hit in hits:
                    scores[hit.document_id] = max(scores.get(hit.document_id, 0), hit.relevance_score)
        if query.strip():
            term = query.strip().casefold()
            rows = [
                row
                for row in rows
                if term in row.title.casefold()
                or term in (row.summary or "").casefold()
                or row.document_id in scores
            ]
            rows.sort(key=lambda row: (scores.get(row.document_id, 0), row.created_at_utc), reverse=True)
        total = len(rows)
        return {
            "items": [
                {**self.knowledge._document(row).model_dump(mode="json"), "relevance_score": scores.get(row.document_id)}
                for row in rows[offset : offset + limit]
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def case_detail(self, document_id: str) -> dict:
        detail = self.knowledge.detail(document_id)
        if detail.document_type != "ACCIDENT_REPORT":
            raise ValueError("document is not an accident report")
        chunks = self.knowledge.document_chunks(document_id)
        if not chunks:
            raise ValueError("document has no indexed content")
        selected = chunks[:30]
        standard_fragments, standard_citations = (
            self.knowledge.search_standards(
                " ".join([detail.title, *detail.risk_tags]),
                min(4, self.knowledge.top_k_max),
            )
            if self.knowledge.rag_manager
            else ([], [])
        )
        payload = self.model.generate_structured(
            load_prompt("case_analysis"),
            {
                "title": detail.title,
                "accident_chunks": [{"text": c.text, "section": c.page_or_section} for c in selected],
                "standards": standard_fragments,
            },
        )
        _guard_standard_references(
            [str(payload.get(key, "")) for key in ("process", "causes", "risks", "prevention")],
            [text for item in standard_fragments for text in (item["title"], item["content"], item["page_or_section"])],
            [detail.title],
        )
        return {
            "document_id": document_id,
            "title": detail.title,
            **{key: str(payload.get(key, "原文未说明。")) for key in ("process", "causes", "risks", "prevention")},
            "citations": [_citation(c) for c in selected] + [item.model_dump(mode="json") for item in standard_citations],
        }

    def document_fragments(self, document_id: str) -> dict:
        detail = self.knowledge.detail(document_id)
        chunks = self.knowledge.document_chunks(document_id)
        return {
            "document_id": document_id,
            "title": detail.title,
            "items": [{"content": chunk.text, "citation": _citation(chunk)} for chunk in chunks[:30]],
        }

    def create_training(self, request: TrainingCreate) -> TrainingResponse:
        with self.database.session() as session:
            report = LearningRepository(session).get_report(request.report_id)
            if not report or report.status != "CONFIRMED":
                raise ValueError("training requires a confirmed report")
            report_snapshot = {"statistics": report.statistics_json, "content": report.content_json}
        selected = []
        for document_id in dict.fromkeys(request.document_ids):
            detail = self.knowledge.detail(document_id)
            chunks = self.knowledge.document_chunks(document_id)
            selected.append({
                "document_id": document_id,
                "title": detail.title,
                "document_type": detail.document_type,
                "version_no": detail.current_version,
                "validity_status": detail.validity_status,
                "chunks": [{"content": c.text, "section": c.page_or_section, "chunk_id": c.chunk_id} for c in chunks[:6]],
            })
        if self.knowledge.rag_manager:
            standard_fragments, standard_citations = self.knowledge.search_standards(
                "施工安全 " + " ".join(_RISK_LABELS.get(code, code) for code in report_snapshot["statistics"]["by_type"]),
                min(4, self.knowledge.top_k_max),
            )
            selected_ids = {doc["document_id"] for doc in selected}
            for fragment, citation in zip(standard_fragments, standard_citations):
                if citation.document_id in selected_ids:
                    continue
                selected.append({
                    "document_id": citation.document_id,
                    "title": citation.title,
                    "document_type": "STANDARD",
                    "version_no": citation.version_no,
                    "validity_status": fragment["validity_status"],
                    "auto_retrieved": True,
                    "chunks": [{"content": fragment["content"], "section": citation.page_or_section, "chunk_id": citation.chunk_id}],
                })
                selected_ids.add(citation.document_id)
        report_content = report_snapshot["content"]
        generation_context = {"report": report_content, "documents": selected, "question_count": request.question_count}
        instruction = load_prompt("training_generation", question_count=request.question_count)
        generated = self.model.generate_structured(instruction, generation_context)
        material = str(generated.get("material", "")).strip()
        questions = [TrainingQuestion.model_validate(item) for item in generated.get("questions", [])]
        if not material or len(questions) != request.question_count:
            raise ValueError("培训内容或题目数量不完整，请补充案例、规范资料或减少题数")
        row = TrainingTaskModel(
            task_id=str(uuid4()),
            report_id=request.report_id,
            status="DRAFT",
            title=request.title,
            target_count=request.target_count,
            question_count=request.question_count,
            pass_score=request.pass_score,
            selected_documents_json=selected,
            material=material,
            questions_json=[q.model_dump() for q in questions],
            created_at_utc=_now(),
        )
        with self.database.session() as session:
            LearningRepository(session).add_training_task(row)
        return self._task(row)

    def list_training(self) -> list[TrainingResponse]:
        with self.database.session() as session:
            return [self._task(row) for row in LearningRepository(session).list_training_tasks(limit=100)]

    def get_training(self, task_id: str) -> TrainingResponse:
        with self.database.session() as session:
            row = LearningRepository(session).get_training_task(task_id)
            if not row:
                raise KeyError("training task not found")
            return self._task(row)

    def delete_training(self, task_id: str) -> None:
        with self.database.session() as session:
            repo = LearningRepository(session)
            row = repo.get_training_task(task_id)
            if not row:
                raise KeyError("training task not found")
            repo.delete_training_task(row)

    def edit_training(self, task_id: str, request: TrainingEdit) -> TrainingResponse:
        with self.database.session() as session:
            row = LearningRepository(session).get_training_task(task_id)
            if not row:
                raise KeyError("training task not found")
            if row.status != "DRAFT":
                raise ValueError("published training cannot be edited")
            row.title, row.target_count, row.pass_score, row.material = request.title, request.target_count, request.pass_score, request.material
            row.question_count = len(request.questions)
            row.questions_json = [q.model_dump() for q in request.questions]
            session.flush()
            return self._task(row)

    def publish_training(self, task_id: str) -> TrainingResponse:
        if not self.public_base_url:
            raise ValueError("LEARNING_PUBLIC_BASE_URL must be configured")
        with self.database.session() as session:
            row = LearningRepository(session).get_training_task(task_id)
            if not row:
                raise KeyError("training task not found")
            if row.status != "DRAFT":
                raise ValueError("training task is already published")
            row.access_token = secrets.token_urlsafe(24)
            row.status, row.published_at_utc = "PUBLISHED", _now()
            session.flush()
            training = self._task(row)
        if self.notification_service is not None:
            self.notification_service.notify_training_published(training)
        return training

    def _task(self, row: TrainingTaskModel) -> TrainingResponse:
        url = build_training_public_url(self.public_base_url, self.app_base_path, row.access_token)
        qr_url = build_training_qr_url(self.app_base_path, row.task_id, bool(url))
        return TrainingResponse(
            task_id=row.task_id,
            report_id=row.report_id,
            status=row.status,
            title=row.title,
            target_count=row.target_count,
            question_count=row.question_count,
            pass_score=row.pass_score,
            selected_documents=[
                {key: doc[key] for key in ("document_id", "title", "document_type", "version_no", "validity_status")}
                for doc in (row.selected_documents_json or [])
            ],
            material=row.material,
            questions=[TrainingQuestion.model_validate(q) for q in row.questions_json],
            public_url=url,
            qr_url=qr_url,
        )

    def qr_png(self, task_id: str) -> bytes:
        task = self.get_training(task_id)
        if not task.public_url:
            raise ValueError("training task is not published")
        return generate_training_qr_png(task.public_url)

    def public_task(self, token: str) -> dict:
        with self.database.session() as session:
            row = LearningRepository(session).get_published_training_by_token(token)
            if not row:
                raise KeyError("training task not found")
            return {
                "title": row.title,
                "material": row.material,
                "questions": [{"stem": q["stem"], "options": q["options"]} for q in row.questions_json],
                "question_count": row.question_count,
            }

    def submit(self, token: str, payload: WorkerSubmit) -> WorkerResult:
        worker_id, worker_name = payload.worker_id.strip(), payload.worker_name.strip()
        if not worker_id or not worker_name:
            raise ValueError("worker ID and name are required")
        try:
            with self.database.session() as session:
                repo = LearningRepository(session)
                row = repo.get_published_training_by_token(token)
                if not row:
                    raise KeyError("training task not found")
                if len(payload.answers) != len(row.questions_json) or any(a < 0 or a >= len(q["options"]) for a, q in zip(payload.answers, row.questions_json)):
                    raise ValueError("answers do not match the published questions")
                if repo.has_worker_submitted(row.task_id, worker_id):
                    raise RuntimeError("worker has already submitted this task")
                correct = sum(answer == question["answer"] for answer, question in zip(payload.answers, row.questions_json))
                score = round(100 * correct / len(row.questions_json))
                passed = score >= row.pass_score
                repo.add_training_submission(
                    TrainingSubmissionModel(
                        submission_id=str(uuid4()),
                        task_id=row.task_id,
                        worker_id=worker_id,
                        worker_name=worker_name,
                        answers_json=payload.answers,
                        score=score,
                        passed=passed,
                        submitted_at_utc=_now(),
                    )
                )
            return WorkerResult(score=score, passed=passed)
        except IntegrityError as exc:
            raise RuntimeError("worker has already submitted this task") from exc

    def training_statistics(self, task_id: str) -> dict:
        with self.database.session() as session:
            repo = LearningRepository(session)
            task = repo.get_training_task(task_id)
            if not task:
                raise KeyError("training task not found")
            submissions = repo.list_training_submissions(task_id)
            completed = len(submissions)
            return {
                "target_count": task.target_count,
                "completed_count": completed,
                "completion_rate": min(100, round(100 * completed / task.target_count, 1)),
                "excess_completed_count": max(0, completed - task.target_count),
                "average_score": round(sum(item.score for item in submissions) / completed, 1) if completed else 0,
                "pass_rate": round(100 * sum(item.passed for item in submissions) / completed, 1) if completed else 0,
                "submissions": [
                    {
                        "worker_id": item.worker_id,
                        "worker_name": item.worker_name,
                        "score": item.score,
                        "passed": item.passed,
                        "submitted_at_utc": _as_utc(item.submitted_at_utc).isoformat(),
                    }
                    for item in submissions
                ],
            }
