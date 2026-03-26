"""
FastAPI application — PDF Regulator
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
    """Cleans up storage files older than 1 hour, running every hour."""
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
                            logging.error(f"Cleanup loop: Error deleting {p}: {e}")
                except Exception as e:
                    logging.error(f"Cleanup loop: Error reading stat for {p}: {e}")
        except Exception as e:
            logging.error(f"Cleanup loop general error: {e}")
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — check storage directory and start cleanup task."""
    STORAGE_DIR.mkdir(exist_ok=True)
    init_db()
    cleanup_orphan_tasks()
    
    cleanup_task = asyncio.create_task(cleanup_old_files())
    yield
    cleanup_task.cancel()

app = FastAPI(
    title="PDF Regulator",
    description="Professional PDF tool to extract, rotate, and optimize pages with advanced text recognition and cleanup.",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register routers
app.include_router(upload.router)
app.include_router(pages.router)
app.include_router(extract.router)
app.include_router(download.router)

# Jinja2 template engine
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
async def index(request: Request):
    """Home page."""
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
