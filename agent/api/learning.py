from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from agent.contracts.learning import CaseDetail, ReportContent, ReportCreate, ReportResponse, TrainingCreate, TrainingEdit, TrainingResponse, WorkerResult, WorkerSubmit
from agent.services.learning_service import LearningConflictError

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])
public_router = APIRouter(prefix="/api/v1/learn", tags=["learning-public"])
logger = logging.getLogger(__name__)


def _service(request: Request):
    return request.app.state.learning_service


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError): return HTTPException(404, str(exc))
    if isinstance(exc, LearningConflictError): return HTTPException(409, str(exc))
    if isinstance(exc, RuntimeError) and "already submitted" in str(exc): return HTTPException(409, str(exc))
    if isinstance(exc, ValueError): return HTTPException(422, str(exc))
    logger.exception("Learning center operation failed")
    return HTTPException(503, "learning operation failed")


@router.post("/reports", response_model=ReportResponse, status_code=201)
def create_report(payload: ReportCreate, request: Request):
    try: return _service(request).create_report(payload)
    except Exception as exc: raise _error(exc) from exc


@router.get("/reports", response_model=list[ReportResponse])
def list_reports(request: Request): return _service(request).list_reports()


@router.get("/overview")
def weekly_overview(request: Request):
    try: return _service(request).weekly_overview()
    except Exception as exc: raise _error(exc) from exc


@router.get("/overview/insights")
def weekly_insights(request: Request, refresh: bool = False):
    try: return _service(request).weekly_insights(refresh=refresh)
    except Exception as exc: raise _error(exc) from exc


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, request: Request):
    try: return _service(request).get_report(report_id)
    except Exception as exc: raise _error(exc) from exc


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: str, request: Request):
    try: _service(request).delete_report(report_id)
    except Exception as exc: raise _error(exc) from exc


@router.get("/reports/{report_id}/pdf")
def report_pdf(report_id: str, request: Request):
    try: return FileResponse(_service(request).pdf_path(report_id), media_type="application/pdf", filename=f"safety-report-{report_id}.pdf")
    except Exception as exc: raise _error(exc) from exc


@router.put("/reports/{report_id}", response_model=ReportResponse)
def edit_report(report_id: str, payload: ReportContent, request: Request):
    try: return _service(request).edit_report(report_id, payload)
    except Exception as exc: raise _error(exc) from exc


@router.post("/reports/{report_id}:confirm", response_model=ReportResponse)
def confirm_report(report_id: str, request: Request):
    try: return _service(request).confirm_report(report_id)
    except Exception as exc: raise _error(exc) from exc


@router.get("/documents")
def search_documents(request: Request, query: str = Query(default="", max_length=200), risk_type: str | None = Query(default=None, max_length=64), document_type: str | None = Query(default=None, pattern="^(STANDARD|ACCIDENT_REPORT)$"), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0), date_start: datetime | None = None, date_end: datetime | None = None):
    try: return _service(request).search_documents(query, risk_type, document_type, limit, offset, date_start, date_end)
    except Exception as exc: raise _error(exc) from exc


@router.get("/documents/{document_id}/case-detail", response_model=CaseDetail)
def case_detail(document_id: str, request: Request):
    try: return _service(request).case_detail(document_id)
    except Exception as exc: raise _error(exc) from exc


@router.get("/documents/{document_id}/fragments")
def document_fragments(document_id: str, request: Request):
    try: return _service(request).document_fragments(document_id)
    except Exception as exc: raise _error(exc) from exc


@router.post("/training", response_model=TrainingResponse, status_code=201)
def create_training(payload: TrainingCreate, request: Request):
    try: return _service(request).create_training(payload)
    except Exception as exc: raise _error(exc) from exc


@router.get("/training", response_model=list[TrainingResponse])
def list_training(request: Request): return _service(request).list_training()


@router.get("/training/{task_id}", response_model=TrainingResponse)
def get_training(task_id: str, request: Request):
    try: return _service(request).get_training(task_id)
    except Exception as exc: raise _error(exc) from exc


@router.delete("/training/{task_id}", status_code=204)
def delete_training(task_id: str, request: Request):
    try: _service(request).delete_training(task_id)
    except Exception as exc: raise _error(exc) from exc


@router.put("/training/{task_id}", response_model=TrainingResponse)
def edit_training(task_id: str, payload: TrainingEdit, request: Request):
    try: return _service(request).edit_training(task_id, payload)
    except Exception as exc: raise _error(exc) from exc


@router.post("/training/{task_id}:publish", response_model=TrainingResponse)
def publish_training(task_id: str, request: Request):
    try: return _service(request).publish_training(task_id)
    except Exception as exc: raise _error(exc) from exc


@router.get("/training/{task_id}/statistics")
def training_statistics(task_id: str, request: Request):
    try: return _service(request).training_statistics(task_id)
    except Exception as exc: raise _error(exc) from exc


@router.get("/training/{task_id}/qr")
def training_qr(task_id: str, request: Request):
    try: return Response(_service(request).qr_png(task_id), media_type="image/png")
    except Exception as exc: raise _error(exc) from exc


@public_router.get("/{token}")
def public_task(token: str, request: Request):
    try: return _service(request).public_task(token)
    except Exception as exc: raise _error(exc) from exc


@public_router.post("/{token}/submissions", response_model=WorkerResult, status_code=201)
def submit(token: str, payload: WorkerSubmit, request: Request):
    try: return _service(request).submit(token, payload)
    except Exception as exc: raise _error(exc) from exc
