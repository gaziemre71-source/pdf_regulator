"""
Extract endpoint — POST /extract
Extracts the selected page range as a new PDF.
Response: HTML fragment added to the left panel via HTMX.
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
import uuid

from backend.services import pdf_service
from backend import database

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates")
)


ALLOWED_OCR_LANGS = {"tur", "eng", "tur+eng"}

class ExtractRequest(BaseModel):
    pdf_id: str
    page_indices: list[int]  # 0-based list of selected pages
    rotations: dict[int, int] = {} # page_index: angle
    ocr: bool = False
    ocr_lang: str = "tur+eng"  # Tesseract language(s): "tur", "eng", or "tur+eng"


@router.post("/extract")
async def extract_pages(req: ExtractRequest, background_tasks: BackgroundTasks, request: Request):
    """Extracts selected pages, returns the left panel HTML fragment."""
    if not req.page_indices:
        raise HTTPException(status_code=400, detail="No pages selected.")

    try:
        file_id, filename = pdf_service.extract_pages(
            req.pdf_id, req.page_indices, req.rotations
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source PDF not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction error: {e}")

    count = len(req.page_indices)
    label = f"{count} Pages" if count > 1 else f"Page {req.page_indices[0] + 1}"

    if req.ocr:
        lang = req.ocr_lang if req.ocr_lang in ALLOWED_OCR_LANGS else "tur+eng"
        task_id = "TASK_" + uuid.uuid4().hex
        input_path = pdf_service.get_output_path(file_id)
        
        database.create_task(task_id, filename, label)
        background_tasks.add_task(pdf_service.perform_ocr, task_id, input_path, filename, lang)
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(task_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/pdf_item.html",
        context={
            "request": request,
            "file_id": file_id,
            "filename": filename,
            "label": label,
        },
    )

@router.get("/extract-status/{task_id}")
async def get_extract_status(task_id: str, request: Request):
    """Returns the status of OCR performed during extraction."""
    task = database.get_task(task_id)
    if not task:
        return {"status": "error", "error": "Task not found."}
    
    status = task.get("status")
    if status in ["pending", "processing"]:
        return {"status": status}
    elif status == "failed":
        return {"status": "error", "error": task.get("error_message", "Unknown Error")}
    elif status == "done":
        pdf_id = task.get("pdf_id")
        filename = task.get("filename")
        label = task.get("label", "OCR Result")
        
        html_response = templates.TemplateResponse(
            request=request,
            name="partials/pdf_item.html",
            context={
                "request": request,
                "file_id": pdf_id,
                "filename": filename,
                "label": label,
            },
        )
        return {"status": "done", "html": html_response.body.decode('utf-8')}
