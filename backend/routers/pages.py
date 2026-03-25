"""
Sayfa render endpoint — GET /page/{pdf_id}/{page_number}
PNG olarak sayfa görüntüsü döner.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.services import pdf_service

router = APIRouter()


@router.get("/page/{pdf_id}/{page_number}")
async def get_page_image(pdf_id: str, page_number: int):
    """Belirtilen sayfayı PNG olarak döner."""
    try:
        png_path = pdf_service.render_page(pdf_id, page_number)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF bulunamadı.")
    except IndexError:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sayfa render hatası: {e}")

    return FileResponse(path=str(png_path), media_type="image/png")
