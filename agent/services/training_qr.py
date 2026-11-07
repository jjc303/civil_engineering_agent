"""Training task QR code generation and public URL resolution (SRP)."""
from __future__ import annotations

import io
from typing import Optional


def build_training_public_url(
    public_base_url: str,
    app_base_path: str,
    public_token: Optional[str],
) -> Optional[str]:
    """Construct the public worker H5 quiz URL."""
    if not public_token:
        return None
    base = public_base_url.rstrip("/") if public_base_url else app_base_path.rstrip("/")
    return f"{base}/learn/{public_token}"


def build_training_qr_url(
    app_base_path: str,
    task_id: str,
    has_public_url: bool,
) -> Optional[str]:
    """Construct the QR PNG endpoint URL if published."""
    if not has_public_url:
        return None
    base = app_base_path.rstrip("/")
    return f"{base}/api/v1/learning/training/{task_id}/qr"


def generate_training_qr_png(public_url: str) -> bytes:
    """Generate a PNG image containing the QR code for a public training task."""
    import qrcode

    if not public_url:
        raise ValueError("training task is not published")
    output = io.BytesIO()
    qrcode.make(public_url).save(output, format="PNG")
    return output.getvalue()
