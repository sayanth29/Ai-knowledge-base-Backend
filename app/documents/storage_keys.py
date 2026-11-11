
from uuid import UUID


def generate_document_storage_key(
    company_id:UUID,
    document_id:UUID,
)->str:
    return  f"{company_id}/{document_id}.pdf"

