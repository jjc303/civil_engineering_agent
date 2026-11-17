from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from agent.api.dependencies import get_request_locale
from agent.domain.violation_catalog import dictionaries_payload
from agent.i18n import SupportedLocale, localize_response

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/dictionaries")
def get_dictionaries(locale: SupportedLocale = Depends(get_request_locale)) -> dict[str, Any]:
    return localize_response(dictionaries_payload(), locale)
