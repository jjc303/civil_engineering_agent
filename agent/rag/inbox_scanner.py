"""Knowledge inbox directory scanner for document ingestion (SRP)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from agent.contracts.knowledge import DocumentType


@dataclass(frozen=True)
class InboxCandidateFile:
    path: Path
    relative_path: Path
    document_type: DocumentType
    content: bytes
    checksum: str
    source_label: str


def scan_inbox_candidates(
    inbox_dir: Path,
    allowed_extensions: Sequence[str] | set[str],
    max_upload_bytes: int,
    type_by_subdirectory: Mapping[str, DocumentType],
) -> list[InboxCandidateFile]:
    """Scan inbox directory tree, filtering files and computing SHA-256 digests."""
    allowed = {ext.lower() for ext in allowed_extensions}
    inbox_root = inbox_dir.resolve()
    candidates: list[InboxCandidateFile] = []

    if not inbox_dir.is_dir():
        return candidates

    for path in sorted(inbox_dir.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.suffix.lower() not in allowed
            or path.name.lower() == "readme.md"
        ):
            continue

        try:
            resolved = path.resolve()
            relative = resolved.relative_to(inbox_root)
            if len(relative.parts) < 2 or relative.parts[0] not in type_by_subdirectory:
                continue

            content = path.read_bytes()
            if not content or len(content) > max_upload_bytes:
                continue

            checksum = hashlib.sha256(content).hexdigest()
            source_label = f"inbox/{relative.as_posix()}"[:512]
            doc_type = type_by_subdirectory[relative.parts[0]]

            candidates.append(
                InboxCandidateFile(
                    path=path,
                    relative_path=relative,
                    document_type=doc_type,
                    content=content,
                    checksum=checksum,
                    source_label=source_label,
                )
            )
        except Exception:
            continue

    return candidates
