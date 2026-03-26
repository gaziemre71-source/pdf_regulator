"""
FastAPI uygulaması — PDF Selector & Rotator
"""
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import asyncio
import time
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging

from backend.routers import upload, pages, extract, download
from backend.services.pdf_service import STORAGE_DIR, is_file_locked
from backend.database import init_db, cleanup_orphan_tasks

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"


async def cleanup_old_files():
    """Her saat başı, 1 saatten eski storage dosyalarını temizler."""
    import itertools
    while True:
        try:
            now = time.time()
            for p in itertools.chain(STORAGE_DIR.glob("*.pdf"), STORAGE_DIR.glob("*.png")):
                try:
                    if now - p.stat().st_mtime > 3600:
                        if is_file_locked(p):
                            continue
                        try:
                            p.unlink()
                        except Exception as e:
                            logging.error(f"Cleanup loop: {p} silinirken hata oluştu: {e}")
                except Exception as e:
                    logging.error(f"Cleanup loop: {p} statokunurken hata oluştu: {e}")
        except Exception as e:
            logging.error(f"Cleanup loop genel hata: {e}")
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü — storage dizinini kontrol et ve temizlik görevini başlat."""
    STORAGE_DIR.mkdir(exist_ok=True)
    init_db()
    cleanup_orphan_tasks()
    
    cleanup_task = asyncio.create_task(cleanup_old_files())
    yield
    cleanup_task.cancel()

app = FastAPI(
    title="PDF Selector & Rotator",
    description="Sayfa seçimi, çıkarma ve döndürme için hafif PDF aracı.",
    version="1.0.0",
    lifespan=lifespan,
)

# Statik dosyalar
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Router'ları kaydet
app.include_router(upload.router)
app.include_router(pages.router)
app.include_router(extract.router)
app.include_router(download.router)

# Jinja2 template motoru
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
async def index(request: Request):
    """Ana sayfa."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
