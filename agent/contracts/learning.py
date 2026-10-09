from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator


class ReportCreate(BaseModel):
    period_start_utc: datetime
    period_end_utc: datetime

    @model_validator(mode="after")
    def check_period(self):
        self.period_start_utc = self.period_start_utc.replace(tzinfo=timezone.utc) if self.period_start_utc.tzinfo is None else self.period_start_utc.astimezone(timezone.utc)
        self.period_end_utc = self.period_end_utc.replace(tzinfo=timezone.utc) if self.period_end_utc.tzinfo is None else self.period_end_utc.astimezone(timezone.utc)
        if self.period_end_utc <= self.period_start_utc:
            raise ValueError("report end must be after start")
        return self


class ReportContent(BaseModel):
    summary: str = Field(min_length=1)
    risk_analysis: str = Field(min_length=1)
    remediation: str = Field(min_length=1)


class ReportResponse(BaseModel):
    report_id: str
    period_start_utc: datetime
    period_end_utc: datetime
    status: str
    statistics: dict
    citations: list[dict]
    content: ReportContent
    pdf_url: str | None = None
    created_at_utc: datetime


class CaseDetail(BaseModel):
    document_id: str
    title: str
    process: str
    causes: str
    risks: str
    prevention: str
    citations: list[dict]


class TrainingQuestion(BaseModel):
    stem: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int = Field(ge=0)
    evidence: str | None = None

    @model_validator(mode="after")
    def valid_answer(self):
        if self.answer >= len(self.options):
            raise ValueError("answer is outside options")
        return self


class TrainingCreate(BaseModel):
    report_id: str
    title: str = Field(min_length=1, max_length=255)
    document_ids: list[str] = Field(default_factory=list, max_length=10)
    target_count: int = Field(ge=1)
    question_count: int = Field(default=5, ge=1, le=20)
    pass_score: int = Field(default=80, ge=0, le=100)


class TrainingEdit(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    target_count: int = Field(ge=1)
    pass_score: int = Field(ge=0, le=100)
    material: str = Field(min_length=1)
    questions: list[TrainingQuestion] = Field(min_length=1, max_length=20)


class TrainingResponse(BaseModel):
    task_id: str
    report_id: str
    status: str
    title: str
    target_count: int
    question_count: int
    pass_score: int
    selected_documents: list[dict]
    material: str
    questions: list[TrainingQuestion]
    public_url: str | None = None
    qr_url: str | None = None


class WorkerSubmit(BaseModel):
    worker_id: str = Field(min_length=1, max_length=64)
    worker_name: str = Field(min_length=1, max_length=128)
    answers: list[int]


class WorkerResult(BaseModel):
    score: int
    passed: bool
