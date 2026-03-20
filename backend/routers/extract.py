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
    page_indices: list[int]  # 0-tabanlı seçili sayfalar listesi
    rotations: dict[int, int] = {} # sayfa_indeksi: açı


@router.post("/extract")
async def extract_pages(req: ExtractRequest, request: Request):
    """Seçili sayfaları çıkarır, sol panel HTML parçası döner."""
    if not req.page_indices:
        raise HTTPException(status_code=400, detail="Hiç sayfa seçilmedi.")

    try:
        file_id, filename = pdf_service.extract_pages(
            req.pdf_id, req.page_indices, req.rotations
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Kaynak PDF bulunamadı.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF çıkarma hatası: {e}")

    count = len(req.page_indices)
    label = f"{count} Sayfa" if count > 1 else f"Sayfa {req.page_indices[0] + 1}"

    return templates.TemplateResponse(
        "partials/pdf_item.html",
        {
            "request": request,
            "file_id": file_id,
            "filename": filename,
            "label": label,
        },
    )
