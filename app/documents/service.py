from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.validator import ValidatedDocumentUpload
from app.models.document import Document, DocumentStatus, DocumentVisibility

# Must match the index name in your migration exactly
DUPLICATE_DOCUMENT_CONSTRAINT = "uq_documents_company_visibility_sha256_active"


class DocumentAlreadyExistsError(Exception):
    """Raised when identical content already exists with the same visibility."""


def _get_constraint_name(exc: IntegrityError) -> str | None:
    original = exc.orig
    for candidate in (
        original,
        getattr(original, "__cause__", None),
        getattr(original, "__context__", None),
    ):
        if candidate is None:
            continue
        name = getattr(candidate, "constraint_name", None) or getattr(
            getattr(candidate, "diag", None), "constraint_name", None
        )
        if name:
            return name
    return None


async def ensure_document_not_duplicate(
    db: AsyncSession,
    *,
    company_id: UUID,
    sha256: str,
    visibility: DocumentVisibility,
) -> None:
    """Check for the same content with the same visibility (FAILED ignored)."""
    existing = await db.scalar(
        select(Document.id).where(
            Document.company_id == company_id,
            Document.visibility == visibility,
            Document.sha256 == sha256,
            Document.status != DocumentStatus.FAILED,
        )
    )
    if existing is not None:
        raise DocumentAlreadyExistsError("This document has already been uploaded.")


async def create_document_record(
    db: AsyncSession,
    *,
    document_id: UUID,
    company_id: UUID,
    uploaded_by_user_id: UUID,
    storage_key: str,
    upload: ValidatedDocumentUpload,
    visibility: DocumentVisibility = DocumentVisibility.ALL_MEMBERS,
) -> Document:
    """
    Persist metadata after the file is in S3.
    The CALLER must delete the S3 object if this raises.
    """
    document = Document(
        id=document_id,
        company_id=company_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=upload.filename,
        storage_key=storage_key,
        content_type=upload.content_type,
        file_size=upload.file_size,
        sha256=upload.sha256,
        status=DocumentStatus.QUEUED,
        visibility=visibility,
    )
    db.add(document)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _get_constraint_name(exc) == DUPLICATE_DOCUMENT_CONSTRAINT:
            raise DocumentAlreadyExistsError(
                "This document has already been uploaded."
            ) from exc
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(document)
    return document