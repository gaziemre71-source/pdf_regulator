"""
Download endpoint — GET /download/{file_id}
Üretilen PDF dosyasını indirme olarak sunar.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.services import pdf_service

router = APIRouter()


@router.get("/download/{file_id}")
async def download_pdf(file_id: str):
    """Belirtilen file_id'ye ait PDF dosyasını indirir."""
    try:
        path = pdf_service.get_output_path(file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name.split("_", 1)[1] if "_" in path.name else path.name,
    )
