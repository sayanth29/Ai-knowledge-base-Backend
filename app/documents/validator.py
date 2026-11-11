from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

from fastapi import UploadFile


MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_DOCUMENT_SIZE_MIB = MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)
CHUNK_SIZE = 1024 * 1024  # 1 MiB

PDF_SIGNATURE = b"%PDF-"

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
}

# Unicode categories rejected in filenames:
# Cc = control characters (including C1), Cf = invisible/bidi formatting,
# Zl / Zp = line and paragraph separators
FORBIDDEN_FILENAME_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}


class DocumentUploadValidationError(Exception):
    """Base exception for document upload validation errors."""


class UnsupportedDocumentType(DocumentUploadValidationError):
    """Raised when the uploaded file is not an accepted PDF."""


class DocumentTooLarge(DocumentUploadValidationError):
    """Raised when the uploaded file exceeds the configured size limit."""


@dataclass(frozen=True, slots=True)
class ValidatedDocumentUpload:
    filename: str
    content_type: str
    file_size: int
    sha256: str


def validate_filename(filename: str | None) -> str:
    """Return a safe display filename, or raise a validation error."""

    if not filename:
        raise DocumentUploadValidationError("A filename is required.")

    filename = unicodedata.normalize("NFC", filename)

    # Handle both Windows and Unix-style paths.
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    if not filename:
        raise DocumentUploadValidationError("Invalid filename.")

    if len(filename) > 255:
        raise DocumentUploadValidationError(
            "Filename must not exceed 255 characters."
        )

    if any(
        unicodedata.category(char) in FORBIDDEN_FILENAME_CATEGORIES
        for char in filename
    ):
        raise DocumentUploadValidationError(
            "Filename contains invalid characters."
        )

    if not filename.lower().endswith(".pdf"):
        raise UnsupportedDocumentType("Only PDF files are supported.")

    # Reject names that are only an extension, like ".pdf" or " .pdf".
    if not filename[:-4].strip(" ."):
        raise DocumentUploadValidationError("Invalid filename.")

    return filename


async def validate_pdf_upload(
    upload: UploadFile,
) -> ValidatedDocumentUpload:
    """
    Validate filename, content type, size and PDF signature, and compute
    the SHA-256 in a single streaming pass. The file is rewound afterwards.
    """

    filename = validate_filename(upload.filename)

    declared_content_type = (
        (upload.content_type or "").split(";", 1)[0].strip().lower()
    )

    if declared_content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedDocumentType(
            "Unsupported file content type. Upload a PDF."
        )

    sha256 = hashlib.sha256()
    file_size = 0
    header = bytearray()

    try:
        await upload.seek(0)

        while chunk := await upload.read(CHUNK_SIZE):
            file_size += len(chunk)

            if file_size > MAX_DOCUMENT_SIZE_BYTES:
                raise DocumentTooLarge(
                    f"File exceeds the maximum allowed size of "
                    f"{MAX_DOCUMENT_SIZE_MIB} MiB."
                )

            # Collect enough leading bytes to check the PDF signature.
            if len(header) < len(PDF_SIGNATURE):
                remaining = len(PDF_SIGNATURE) - len(header)
                header.extend(chunk[:remaining])

            sha256.update(chunk)

        if file_size == 0:
            raise UnsupportedDocumentType("Uploaded file is empty.")

        if bytes(header) != PDF_SIGNATURE:
            raise UnsupportedDocumentType("Invalid PDF file signature.")

    finally:
        # Leave the file ready for the next operation (the S3 upload).
        await upload.seek(0)

    return ValidatedDocumentUpload(
        filename=filename,
        content_type="application/pdf",
        file_size=file_size,
        sha256=sha256.hexdigest(),
    )