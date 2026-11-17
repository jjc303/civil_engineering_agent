from __future__ import annotations

import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from agent.api.dependencies import get_knowledge_service as _service, get_request_locale
from agent.contracts.knowledge import DocumentType, StandardValidityUpdate, KnowledgeMetadataUpdate, KnowledgeDocumentDetailResponse, KnowledgeDocumentPage, KnowledgeIndexJobPage, KnowledgeIndexJobResponse
from agent.i18n import SupportedLocale, localize_response

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError): return HTTPException(404, detail=str(exc))
    if isinstance(exc, RuntimeError) and "conflict" in str(exc): return HTTPException(409, detail=str(exc))
    if isinstance(exc, ValueError): return HTTPException(422, detail=str(exc))
    return HTTPException(503, detail="knowledge operation failed")


@router.post("/documents", response_model=KnowledgeDocumentDetailResponse, status_code=201)
async def upload_document(request: Request, file: UploadFile = File(...), title: str = Form(...), source_label: str = Form(""), document_type: DocumentType = Form("ACCIDENT_REPORT"), document_date: datetime | None = Form(None), risk_tags: str = Form(""), summary: str = Form(""), locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try:
        content = await file.read()
        detail, _, duplicate = await asyncio.to_thread(_service(request).upload, filename=file.filename or "upload", content=content, title=title, source_label=source_label or title, actor="admin", document_type=document_type, document_date=document_date, risk_tags=[x.strip() for x in risk_tags.split(",") if x.strip()], summary=summary or None)
        if duplicate: raise HTTPException(409, detail="identical document already exists")
        return localize_response(detail, locale)
    except HTTPException: raise
    except Exception as exc: raise _error(exc) from exc


@router.get("/documents", response_model=KnowledgeDocumentPage)
def list_documents(request: Request, limit: int = 20, offset: int = 0, status: str | None = None, document_type: DocumentType | None = None, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentPage:
    return localize_response(_service(request).list_documents(min(max(limit, 1), 100), max(offset, 0), status, document_type), locale)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetailResponse)
def get_document(document_id: str, request: Request, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try: return localize_response(_service(request).detail(document_id), locale)
    except Exception as exc: raise _error(exc) from exc


@router.patch("/documents/{document_id}/metadata", response_model=KnowledgeDocumentDetailResponse)
def update_metadata(document_id: str, payload: KnowledgeMetadataUpdate, request: Request, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try: return localize_response(_service(request).update_metadata(document_id, payload, "admin"), locale)
    except Exception as exc: raise _error(exc) from exc


@router.post("/documents/{document_id}:summarize", response_model=KnowledgeDocumentDetailResponse)
def regenerate_summary(document_id: str, request: Request, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try: return localize_response(_service(request).summarize_document(document_id, force=True), locale)
    except Exception as exc: raise _error(exc) from exc


@router.post("/documents/{document_id}:classify", response_model=KnowledgeDocumentDetailResponse)
def classify_document(document_id: str, request: Request, document_type: DocumentType, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try: return localize_response(_service(request).classify(document_id, document_type, "admin"), locale)
    except Exception as exc: raise _error(exc) from exc


@router.patch("/documents/{document_id}/validity", response_model=KnowledgeDocumentDetailResponse)
def update_standard_validity(document_id: str, payload: StandardValidityUpdate, request: Request, locale: SupportedLocale = Depends(get_request_locale)) -> KnowledgeDocumentDetailResponse:
    try: return localize_response(_service(request).set_standard_validity(document_id, payload.validity_status, "admin"), locale)
    except Exception as exc: raise _error(exc) from exc


@router.post("/documents/{document_id}/versions", response_model=KnowledgeDocumentDetailResponse, status_code=201)
async def create_version(document_id: str, request: Request, file: UploadFile = File(...), title: str = Form(...), source_label: str = Form(""), expected_current_version: int | None = Form(None)) -> KnowledgeDocumentDetailResponse:
    try:
        content = await file.read()
        detail, _, _ = await asyncio.to_thread(_service(request).upload, filename=file.filename or "upload", content=content, title=title, source_label=source_label or title, actor="admin", document_id=document_id, expected_current_version=expected_current_version)
        return detail
    except Exception as exc: raise _error(exc) from exc


@router.post("/documents/{document_id}:retire", status_code=204)
def retire(document_id: str, request: Request) -> None:
    try: _service(request).retire(document_id, "admin")
    except Exception as exc: raise _error(exc) from exc


@router.post("/documents/{document_id}:activate", response_model=KnowledgeIndexJobResponse)
def activate(document_id: str, version_id: str, request: Request) -> KnowledgeIndexJobResponse:
    try: return _service(request).activate(document_id, version_id, "admin")
    except Exception as exc: raise _error(exc) from exc


@router.post("/versions/{version_id}:reindex", response_model=KnowledgeIndexJobResponse)
def reindex(version_id: str, request: Request) -> KnowledgeIndexJobResponse:
    try: return _service(request).reindex(version_id, "admin")
    except Exception as exc: raise _error(exc) from exc


@router.get("/index-jobs", response_model=KnowledgeIndexJobPage)
def list_jobs(request: Request, limit: int = 20, offset: int = 0, status: str | None = None) -> KnowledgeIndexJobPage:
    return _service(request).jobs(min(max(limit, 1), 100), max(offset, 0), status)


@router.get("/index-jobs/{job_id}", response_model=KnowledgeIndexJobResponse)
def get_job(job_id: str, request: Request) -> KnowledgeIndexJobResponse:
    try: return _service(request).job(job_id)
    except Exception as exc: raise _error(exc) from exc
