"""
Download endpoint — GET /download/{file_id}
Serves the generated PDF file as a download.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.services import pdf_service

router = APIRouter()


@router.get("/download/{file_id}")
async def download_pdf(file_id: str):
    """Downloads the PDF file belonging to the specified file_id."""
    try:
        path = pdf_service.get_output_path(file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name.split("_", 1)[1] if "_" in path.name else path.name,
    )
