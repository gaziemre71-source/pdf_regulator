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
from functools import lru_cache
import contextlib
import logging

ACTIVE_FILE_LOCKS = set()

@contextlib.contextmanager
def lock_file(filepath: Path):
    filepath_str = str(filepath.resolve())
    ACTIVE_FILE_LOCKS.add(filepath_str)
    try:
        yield
    finally:
        ACTIVE_FILE_LOCKS.discard(filepath_str)

def is_file_locked(filepath: Path) -> bool:
    return str(filepath.resolve()) in ACTIVE_FILE_LOCKS

# Geçici dosya dizini
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

def is_valid_uuid(val: str) -> bool:
    """Girilen değerin 32 karakterli hex (UUID) olup olmadığını kontrol eder."""
    return bool(val and len(val) == 32 and val.isalnum())

def save_upload(file_path: Path, original_name: str) -> tuple[str, int]:
    """Yüklenen PDF dosyasını benzersiz pdf_id ile storage'a kaydeder.

    Returns:
        (pdf_id, page_count)
    """
    import shutil
    pdf_id = uuid.uuid4().hex
    dest = STORAGE_DIR / f"{pdf_id}_src.pdf"
    
    STORAGE_DIR.mkdir(exist_ok=True)
    shutil.move(str(file_path), str(dest))

    # Sayfa sayısını al
    with lock_file(dest):
        doc = fitz.open(str(dest))
        page_count = len(doc)
        doc.close()

    return pdf_id, page_count

# OCR Semaphore for controlling concurrency
MAX_CONCURRENT_OCR = 2
OCR_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_OCR)
from backend import database

async def perform_ocr(task_id: str, input_path: Path, original_name: str):
    """Arka planda ocrmypdf kullanarak OCR işlemini gerçekleştirir."""
    success = False
    dest_path = None
    try:
        pdf_id = uuid.uuid4().hex
        dest_path = STORAGE_DIR / f"{pdf_id}_src.pdf"

        # 1. Aşama Optimizasyonu: Sistem kaynaklarını korumak için PyMuPDF ile hızlı metin taraması
        import shutil
        with lock_file(input_path):
            doc = fitz.open(str(input_path))
            needs_ocr = False
            
            for page in doc:
                # Eğer bir sayfada 15 karakterden az metin varsa, o sayfa muhtemelen taranmış bir resimdir.
                if len(page.get_text().strip()) < 15:
                    needs_ocr = True
                    break
                    
            page_count = len(doc)
            doc.close()

        if not needs_ocr:
            # Belgedeki tüm sayfalarda halihazırda yeterli metin var. 
            # OCR işlemini (ocrmypdf) tamamen atla ve dosyayı doğrudan kopyala! (0.01s sürer)
            shutil.copy2(input_path, dest_path)
            
            database.update_task_success(task_id, pdf_id, page_count, original_name)
            success = True
            
            if input_path.exists():
                try:
                    input_path.unlink()
                except Exception:
                    pass
            return

        # 2. Aşama Optimizasyonu: En az 1 resimli sayfa bulunduysa OCR başlat
        try:
            async with OCR_SEMAPHORE:
                proc = await asyncio.create_subprocess_exec(
                    "ocrmypdf",
                    "--skip-text",   # <-- Mixed dokümanlarda sadece resimli sayfaları OCR'dan geçirir
                    "-l", "tur+eng",
                    "--jobs", "1",
                    "--deskew",      # Sayfaları düzeltir (eğikliği giderir)
                    "--clean",       # Gürültü ve artifact'leri temizler
                    "--optimize", "1", # Dosya boyutunu küçültür ve binarize eder
                    "--fast-web-view", "0",
                    str(input_path),
                    str(dest_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode != 0:
                    database.update_task_failure(task_id, stderr.decode('utf-8', errors='replace'))
                    return
        except FileNotFoundError:
            database.update_task_failure(task_id, "OCR motoru (ocrmypdf) sistemde yüklü değil.")
            return
            
        with lock_file(dest_path):
            doc = fitz.open(str(dest_path))
            page_count = len(doc)
            doc.close()
        
        database.update_task_success(task_id, pdf_id, page_count, original_name)
        success = True
        
    except Exception as e:
        database.update_task_failure(task_id, str(e))
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except Exception:
                pass
        if not success and dest_path is not None and dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass



def _src_path(pdf_id: str) -> Path:
    """Kaynak PDF dosyasının yolunu döner."""
    if not is_valid_uuid(pdf_id):
        raise ValueError(f"Geçersiz PDF ID: {pdf_id}")
        
    path = STORAGE_DIR / f"{pdf_id}_src.pdf"
    if not path.exists():
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_id}")
    return path


def render_page(pdf_id: str, page_num: int, dpi: int = 120) -> Path:
    """Belirtilen sayfayı PNG olarak render edip diskte önbelleğe alır ve dosya yolunu döner.
    Sonuç STORAGE_DIR içinde saklanır.

    Args:
        pdf_id: Kaynak PDF kimliği
        page_num: 0-tabanlı sayfa numarası
        dpi: Render çözünürlüğü (varsayılan 120)

    Returns:
        Oluşturulan veya var olan PNG dosyasının Path nesnesi
    """
    path = _src_path(pdf_id)
    out_path = STORAGE_DIR / f"{pdf_id}_page_{page_num}_{dpi}.png"

    if out_path.exists():
        return out_path

    with lock_file(path):
        doc = fitz.open(str(path))
        try:
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            
            with open(out_path, "wb") as f:
                f.write(png_bytes)
        finally:
            doc.close()

    return out_path


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
    with lock_file(src_path):
        src_doc = fitz.open(str(src_path))
    
        # Sayfa sayısını doğrula ve geçersizleri ayıkla
        total = len(src_doc)
        valid_indices = [idx for idx in page_indices if 0 <= idx < total]
        
        if not valid_indices:
             src_doc.close()
             raise ValueError("Hiç geçerli sayfa seçilmedi.")
    
        if len(valid_indices) > 500:
             src_doc.close()
             raise ValueError("Sistem performansını korumak için, tek seferde en fazla 500 sayfa çıkarılabilir.")
    
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
    if not is_valid_uuid(file_id):
        raise ValueError(f"Geçersiz File ID: {file_id}")
        
    matches = list(STORAGE_DIR.glob(f"{file_id}_*.pdf"))
    if not matches:
        raise FileNotFoundError(f"Çıktı dosyası bulunamadı: {file_id}")
    return matches[0]
