from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
import json
import uuid
import os
import tempfile

from backend.services import pdf_service

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates")
)


@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """PDF veya Resim dosyasını yükler, viewer HTML parçasını döner."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dosya yüklenemedi.")

    fd, temp_path = tempfile.mkstemp()
    temp_pdf_path = None
    try:
        file_size = 0
        with os.fdopen(fd, 'wb') as out_file:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                if file_size > 100 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Dosya boyutu 100MB sınırını aşıyor.")
                out_file.write(chunk)

        if file_size < 4:
            raise HTTPException(status_code=400, detail="Boş dosya yüklendi.")

        from backend.services.preprocessor import preprocess_to_pdf
        pdf_path, final_filename = preprocess_to_pdf(Path(temp_path), file.filename)
        temp_pdf_path = str(pdf_path)

        pdf_id, page_count = pdf_service.save_upload(pdf_path, final_filename)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF kaydedilemedi: {e}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        
        if temp_pdf_path and temp_pdf_path != temp_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except Exception:
                pass

    response = templates.TemplateResponse(
        "partials/viewer.html",
        {
            "request": request,
            "pdf_id": pdf_id,
            "page_count": page_count,
            "filename": final_filename,
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

@router.get("/ocr-status/{task_id}")
async def get_ocr_status(request: Request, task_id: str):
    task = pdf_service.OCR_TASKS.get(task_id)
    if not task:
        return HTMLResponse("<div class='text-red-500 flex justify-center items-center h-full'>Task bulunamadı.</div>")
    
    status = task.get("status")
    
    if status in ["pending", "processing"]:
        return HTMLResponse(f"""
        <div id="viewer-inner" class="flex flex-col items-center justify-center h-full gap-4 text-gray-400"
             hx-get="/ocr-status/{task_id}" hx-trigger="every 1.5s" hx-swap="outerHTML">
            <svg class="w-12 h-12 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <p class="text-lg font-semibold animate-pulse">OCR İşlemi Yapılıyor...</p>
            <p class="text-sm">Bu işlem dosya boyutuna göre birkaç dakika sürebilir.</p>
        </div>
        """)
        
    elif status == "failed":
        err = task.get("error", "Bilinmeyen Hata")
        return HTMLResponse(f"<div class='text-red-500 flex justify-center items-center h-full'>OCR Hatası: {err}</div>")
        
    elif status == "done":
        pdf_id = task.get("pdf_id")
        page_count = task.get("page_count")
        filename = task.get("filename")
        
        response = templates.TemplateResponse(
            "partials/viewer.html",
            {
                "request": request,
                "pdf_id": pdf_id,
                "page_count": page_count,
                "filename": filename,
            },
        )
        response.headers["HX-Trigger"] = json.dumps({
            "viewerReady": {
                "pdfId": pdf_id, 
                "pageCount": page_count
            }
        })
        return response
