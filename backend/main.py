"""
FastAPI uygulaması — PDF Selector & Rotator
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.routers import upload, pages, extract, download
from backend.services.pdf_service import STORAGE_DIR

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü — storage dizinini kontrol et."""
    STORAGE_DIR.mkdir(exist_ok=True)
    yield


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
    return templates.TemplateResponse("index.html", {"request": request})
