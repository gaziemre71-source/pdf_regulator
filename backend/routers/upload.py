from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

from backend.services import pdf_service

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates")
)


@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """PDF dosyasını yükler, viewer HTML parçasını döner."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece .pdf dosyaları kabul edilir.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Boş dosya yüklendi.")

    try:
        pdf_id, page_count = pdf_service.save_upload(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF kaydedilemedi: {e}")

    response = templates.TemplateResponse(
        "partials/viewer.html",
        {
            "request": request,
            "pdf_id": pdf_id,
            "page_count": page_count,
            "filename": file.filename,
        },
    )
    # HTMX için viewerReady event'ini tetikle
    response.headers["HX-Trigger"] = json.dumps({
        "viewerReady": {
            "pdfId": pdf_id, 
            "pageCount": page_count
        }
    })
    return response
