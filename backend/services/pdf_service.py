"""
PDF işlem servisi — PyMuPDF (fitz) kullanarak:
- PDF yükleme & kaydetme
- Sayfa PNG olarak render etme (bellek önbelleği)
- Sayfa aralığı çıkarma
- Sayfa döndürme
"""
import uuid
import io
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


def extract_pages(pdf_id: str, start_page: int, end_page: int, rotations: dict[int, int] = None) -> tuple[str, str]:
    """Belirtilen sayfa aralığını (dahil) yeni bir PDF dosyası olarak çıkarır
    ve belirtilen açılara göre döndürür.

    Args:
        pdf_id: Kaynak PDF kimliği
        start_page: Başlangıç sayfası (0-tabanlı, dahil)
        end_page: Bitiş sayfası (0-tabanlı, dahil)
        rotations: {sayfa_indeksi: döndürme_açısı} örneğin {0: 90, 1: -90}

    Returns:
        (file_id, filename)
    """
    if rotations is None:
        rotations = {}

    src_path = _src_path(pdf_id)
    src_doc = fitz.open(str(src_path))

    # Sayfa sayısını doğrula
    total = len(src_doc)
    start_page = max(0, min(start_page, total - 1))
    end_page = max(start_page, min(end_page, total - 1))

    new_doc = fitz.open()
    new_doc.insert_pdf(src_doc, from_page=start_page, to_page=end_page)

    # Rotasyonları uygula
    has_rotation = False
    for i, page in enumerate(new_doc):
        # Orijinal PDF'teki sayfa indeksi
        orig_page_idx = start_page + i
        if orig_page_idx in rotations:
            angle = rotations[orig_page_idx]
            if angle != 0:
                page.set_rotation((page.rotation + angle) % 360)
                has_rotation = True

    file_id = uuid.uuid4().hex
    
    # Dosya adına rotasyon bilgisi ekle
    if has_rotation:
        filename = f"rotated_pages_{start_page + 1}_{end_page + 1}.pdf"
    else:
        filename = f"pages_{start_page + 1}_{end_page + 1}.pdf"
        
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
