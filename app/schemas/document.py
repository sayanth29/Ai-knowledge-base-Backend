from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentVisibility


class DocumentResponse(BaseModel):
    """Public document metadata returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    file_size: int

    status: DocumentStatus
    visibility: DocumentVisibility

    page_count: int | None
    chunk_count: int | None

    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """Response returned after a document upload is accepted."""

    document: DocumentResponse
    message: str = "Document uploaded and queued for processing."


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentResponse]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class DocumentVisibilityUpdate(BaseModel):
    """Request schema for updating document visibility."""

    visibility: DocumentVisibility