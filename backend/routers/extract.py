"""
Extract endpoint — POST /extract
Seçili sayfa aralığını yeni PDF olarak çıkarır.
Yanıt: HTMX ile sol panele eklenen HTML parçası.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path

from backend.services import pdf_service

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates")
)


class ExtractRequest(BaseModel):
    pdf_id: str
    start_page: int  # 0-tabanlı
    end_page: int    # 0-tabanlı, dahil
    rotations: dict[int, int] = {} # sayfa_indeksi: açı


@router.post("/extract")
async def extract_pages(req: ExtractRequest, request: Request):
    """Sayfa aralığını çıkarır, sol panel HTML parçası döner."""
    if req.start_page > req.end_page:
        raise HTTPException(status_code=400, detail="start_page > end_page olamaz.")

    try:
        file_id, filename = pdf_service.extract_pages(
            req.pdf_id, req.start_page, req.end_page, req.rotations
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Kaynak PDF bulunamadı.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF çıkarma hatası: {e}")

    return templates.TemplateResponse(
        "partials/pdf_item.html",
        {
            "request": request,
            "file_id": file_id,
            "filename": filename,
            "label": f"Sayfa {req.start_page + 1}–{req.end_page + 1}",
        },
    )
