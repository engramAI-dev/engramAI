from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_documents() -> dict[str, list[str]]:
    """List all indexed documents."""
    # TODO: Query documents table with pagination
    return {"documents": []}


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict[str, str]:
    """Get details for a specific document."""
    # TODO: Fetch document by ID
    return {"message": "not implemented"}
