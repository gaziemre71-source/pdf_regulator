"""
Extract endpoint — POST /extract
Seçili sayfa aralığını yeni PDF olarak çıkarır.
Yanıt: HTMX ile sol panele eklenen HTML parçası.
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
import uuid

from backend.services import pdf_service

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates")
)


class ExtractRequest(BaseModel):
    pdf_id: str
    page_indices: list[int]  # 0-tabanlı seçili sayfalar listesi
    rotations: dict[int, int] = {} # sayfa_indeksi: açı
    ocr: bool = False


@router.post("/extract")
async def extract_pages(req: ExtractRequest, background_tasks: BackgroundTasks, request: Request):
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

    if req.ocr:
        task_id = "TASK_" + uuid.uuid4().hex
        input_path = pdf_service.get_output_path(file_id)
        
        pdf_service.OCR_TASKS[task_id] = {"status": "pending", "label": label}
        background_tasks.add_task(pdf_service.perform_ocr, task_id, input_path, filename)
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(task_id)

    return templates.TemplateResponse(
        "partials/pdf_item.html",
        {
            "request": request,
            "file_id": file_id,
            "filename": filename,
            "label": label,
        },
    )

@router.get("/extract-status/{task_id}")
async def get_extract_status(task_id: str, request: Request):
    """Extraction sırasında yapılan OCR'ın durumunu döner."""
    task = pdf_service.OCR_TASKS.get(task_id)
    if not task:
        return {"status": "error", "error": "Task bulunamadı."}
    
    status = task.get("status")
    if status in ["pending", "processing"]:
        return {"status": status}
    elif status == "failed":
        return {"status": "error", "error": task.get("error", "Bilinmeyen Hata")}
    elif status == "done":
        pdf_id = task.get("pdf_id")
        filename = task.get("filename")
        label = task.get("label", "OCR Sonucu")
        
        html_response = templates.TemplateResponse(
            "partials/pdf_item.html",
            {
                "request": request,
                "file_id": pdf_id,
                "filename": filename,
                "label": label,
            },
        )
        return {"status": "done", "html": html_response.body.decode('utf-8')}
