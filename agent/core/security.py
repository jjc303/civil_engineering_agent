from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings

bearer_scheme = HTTPBearer(auto_error=False)


def verify_internal_token(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if credentials.credentials != settings.internal_perception_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid internal token")


def verify_admin_token(credentials: HTTPAuthorizationCredentials | None, settings: Settings) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AGENT_ADMIN_TOKEN is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing admin bearer token")
    if credentials.credentials != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid admin token")
