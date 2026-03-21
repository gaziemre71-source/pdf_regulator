"""
PDF işlem servisi — PyMuPDF (fitz) kullanarak:
- PDF yükleme & kaydetme
- Sayfa PNG olarak render etme (bellek önbelleği)
- Sayfa aralığı çıkarma
- Sayfa döndürme
"""
import uuid
import io
import asyncio
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF

# Geçici dosya dizini
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

# Sayfa render önbelleği: { (pdf_id, page_num, dpi): bytes }
_page_cache: dict[tuple, bytes] = {}


def save_upload(file_bytes: bytes, original_name: str) -> tuple[str, int]:
    """Yüklenen PDF dosyasını benzersiz pdf_id ile storage'a kaydeder.

    Returns:
        (pdf_id, page_count)
    """
    pdf_id = uuid.uuid4().hex
    dest = STORAGE_DIR / f"{pdf_id}_src.pdf"
    dest.write_bytes(file_bytes)

    # Sayfa sayısını al
    doc = fitz.open(str(dest))
    page_count = len(doc)
    doc.close()

    return pdf_id, page_count

# OCR Task List
OCR_TASKS: dict[str, dict] = {}

async def perform_ocr(task_id: str, input_path: Path, original_name: str):
    """Arka planda ocrmypdf kullanarak OCR işlemini gerçekleştirir."""
    try:
        OCR_TASKS[task_id]["status"] = "processing"
        
        pdf_id = uuid.uuid4().hex
        dest_path = STORAGE_DIR / f"{pdf_id}_src.pdf"
        
        proc = await asyncio.create_subprocess_exec(
            "ocrmypdf",
            "--force-ocr",
            "-l", "tur+eng",
            "--jobs", "4",
            str(input_path),
            str(dest_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            OCR_TASKS[task_id]["status"] = "failed"
            OCR_TASKS[task_id]["error"] = stderr.decode('utf-8', errors='replace')
            return
            
        doc = fitz.open(str(dest_path))
        page_count = len(doc)
        doc.close()
        
        OCR_TASKS[task_id]["status"] = "done"
        OCR_TASKS[task_id]["pdf_id"] = pdf_id
        OCR_TASKS[task_id]["page_count"] = page_count
        OCR_TASKS[task_id]["filename"] = original_name
        
    except Exception as e:
        OCR_TASKS[task_id]["status"] = "failed"
        OCR_TASKS[task_id]["error"] = str(e)
    finally:
        if input_path.exists():
            input_path.unlink()



def _src_path(pdf_id: str) -> Path:
    """Kaynak PDF dosyasının yolunu döner."""
    path = STORAGE_DIR / f"{pdf_id}_src.pdf"
    if not path.exists():
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_id}")
    return path


def render_page(pdf_id: str, page_num: int, dpi: int = 120) -> bytes:
    """Belirtilen sayfayı PNG olarak render edip bytes döner.
    Sonuç bellek önbelleğine alınır.

    Args:
        pdf_id: Kaynak PDF kimliği
        page_num: 0-tabanlı sayfa numarası
        dpi: Render çözünürlüğü (varsayılan 120)

    Returns:
        PNG formatında bytes
    """
    cache_key = (pdf_id, page_num, dpi)
    if cache_key in _page_cache:
        return _page_cache[cache_key]

    path = _src_path(pdf_id)
    doc = fitz.open(str(path))
    try:
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")
    finally:
        doc.close()

    _page_cache[cache_key] = png_bytes
    return png_bytes


def extract_pages(pdf_id: str, page_indices: list[int], rotations: dict[int, int] = None) -> tuple[str, str]:
    """Belirtilen sayfa listesini yeni bir PDF dosyası olarak çıkarır
    ve belirtilen açılara göre döndürür.

    Args:
        pdf_id: Kaynak PDF kimliği
        page_indices: Çıkarılacak sayfa indeksleri listesi (0-tabanlı)
        rotations: {sayfa_indeksi: döndürme_açısı} örneğin {0: 90, 1: -90}

    Returns:
        (file_id, filename)
    """
    if rotations is None:
        rotations = {}

    src_path = _src_path(pdf_id)
    src_doc = fitz.open(str(src_path))

    # Sayfa sayısını doğrula ve geçersizleri ayıkla
    total = len(src_doc)
    valid_indices = [idx for idx in page_indices if 0 <= idx < total]
    
    if not valid_indices:
         src_doc.close()
         raise ValueError("Hiç geçerli sayfa seçilmedi.")

    new_doc = fitz.open()
    
    # Her bir sayfayı tek tek ekle (sırayı korumak için)
    for idx in valid_indices:
        new_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)

    # Rotasyonları uygula
    has_rotation = False
    for i, _ in enumerate(new_doc):
        # Orijinal PDF'teki sayfa indeksi
        orig_page_idx = valid_indices[i]
        if orig_page_idx in rotations:
            angle = rotations[orig_page_idx]
            if angle != 0:
                page = new_doc[i]
                page.set_rotation((page.rotation + angle) % 360)
                has_rotation = True

    file_id = uuid.uuid4().hex
    
    # Dosya adına seçilen sayfa sayısını ekle
    count = len(valid_indices)
    if count == 1:
        label = f"page_{valid_indices[0] + 1}"
    else:
        label = f"{count}_pages"

    if has_rotation:
        filename = f"rotated_{label}.pdf"
    else:
        filename = f"{label}.pdf"
        
    out_path = STORAGE_DIR / f"{file_id}_{filename}"
    new_doc.save(str(out_path))

    new_doc.close()
    src_doc.close()

    return file_id, filename


def get_output_path(file_id: str) -> Path:
    """file_id'ye göre çıktı PDF dosyasının yolunu döner."""
    matches = list(STORAGE_DIR.glob(f"{file_id}_*.pdf"))
    if not matches:
        raise FileNotFoundError(f"Çıktı dosyası bulunamadı: {file_id}")
    return matches[0]
