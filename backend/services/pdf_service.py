"""
PDF processing service — using PyMuPDF (fitz):
- PDF upload & save
- Render page as PNG (memory cache)
- Extract page range
- Rotate page
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

# Temporary file directory
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

def is_valid_uuid(val: str) -> bool:
    """Checks if the entered value is a 32-character hex (UUID)."""
    return bool(val and len(val) == 32 and val.isalnum())

def save_upload(file_path: Path, original_name: str) -> tuple[str, int]:
    """Saves the uploaded PDF file to storage with a unique pdf_id.

    Returns:
        (pdf_id, page_count)
    """
    import shutil
    pdf_id = uuid.uuid4().hex
    dest = STORAGE_DIR / f"{pdf_id}_src.pdf"
    
    STORAGE_DIR.mkdir(exist_ok=True)
    shutil.move(str(file_path), str(dest))

    # Get page count
    with lock_file(dest):
        doc = fitz.open(str(dest))
        page_count = len(doc)
        doc.close()

    return pdf_id, page_count

# OCR Semaphore for controlling concurrency
MAX_CONCURRENT_OCR = 2
OCR_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_OCR)
from backend import database

async def perform_ocr(task_id: str, input_path: Path, original_name: str, ocr_lang: str = "tur+eng"):
    """Performs OCR in the background using ocrmypdf."""
    success = False
    dest_path = None
    try:
        pdf_id = uuid.uuid4().hex
        dest_path = STORAGE_DIR / f"{pdf_id}_src.pdf"

        # Phase 1 Optimization: Fast text scanning with PyMuPDF to conserve system resources
        import shutil
        with lock_file(input_path):
            doc = fitz.open(str(input_path))
            needs_ocr = False
            
            for page in doc:
                # If a page has less than 15 characters of text, it is likely a scanned image.
                if len(page.get_text().strip()) < 15:
                    needs_ocr = True
                    break
                    
            page_count = len(doc)
            doc.close()

        if not needs_ocr:
            # All pages in the document already have sufficient text. 
            # Skip the OCR process completely and copy the file directly! (takes ~0.01s)
            shutil.copy2(input_path, dest_path)
            
            database.update_task_success(task_id, pdf_id, page_count, original_name)
            success = True
            
            if input_path.exists():
                try:
                    input_path.unlink()
                except Exception:
                    pass
            return

        # Phase 2 Optimization: Start OCR if at least 1 image page is found
        try:
            async with OCR_SEMAPHORE:
                proc = await asyncio.create_subprocess_exec(
                    "ocrmypdf",
                    "--skip-text",   # Run OCR only on image pages in mixed documents
                    "-l", ocr_lang,
                    # Speed optimization: Removed --jobs 1, all CPU cores will be used
                    # Commented out --deskew and --clean because they slow down process significantly
                    # "--deskew",      # Fixes page orientation (deskew) -> VERY SLOW
                    # "--clean",       # Cleans noise -> VERY SLOW
                    "--optimize", "0", # Reduces file size. 0 for HF
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
            database.update_task_failure(task_id, "OCR engine (ocrmypdf) is not installed on the system.")
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
    """Returns the path of the source PDF file."""
    if not is_valid_uuid(pdf_id):
        raise ValueError(f"Invalid PDF ID: {pdf_id}")
        
    path = STORAGE_DIR / f"{pdf_id}_src.pdf"
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_id}")
    return path


def render_page(pdf_id: str, page_num: int, dpi: int = 120) -> Path:
    """Renders the specified page as PNG, caches it on disk, and returns the file path.
    The result is stored in STORAGE_DIR.

    Args:
        pdf_id: Source PDF ID
        page_num: 0-based page number
        dpi: Render resolution (default 120)

    Returns:
        Path object of the created or existing PNG file
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
    """Extracts the specified list of pages as a new PDF file
    and rotates them according to the specified angles.

    Args:
        pdf_id: Source PDF ID
        page_indices: List of page indices to extract (0-based)
        rotations: {page_index: rotation_angle} e.g. {0: 90, 1: -90}

    Returns:
        (file_id, filename)
    """
    if rotations is None:
        rotations = {}

    src_path = _src_path(pdf_id)
    with lock_file(src_path):
        src_doc = fitz.open(str(src_path))
    
        # Validate page count and filter out invalid ones
        total = len(src_doc)
        valid_indices = [idx for idx in page_indices if 0 <= idx < total]
        
        if not valid_indices:
             src_doc.close()
             raise ValueError("No valid pages selected.")
    
        if len(valid_indices) > 500:
             src_doc.close()
             raise ValueError("To protect system performance, a maximum of 500 pages can be extracted at once.")
    
        new_doc = fitz.open()
        
        # Add each page one by one (to preserve order)
        for idx in valid_indices:
            new_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)
    
        # Apply rotations
        has_rotation = False
        for i, _ in enumerate(new_doc):
            # Page index in original PDF
            orig_page_idx = valid_indices[i]
            if orig_page_idx in rotations:
                angle = rotations[orig_page_idx]
                if angle != 0:
                    page = new_doc[i]
                    page.set_rotation((page.rotation + angle) % 360)
                    has_rotation = True
    
        file_id = uuid.uuid4().hex
        
        # Append selected page count to filename
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
    """Returns the output PDF file path according to file_id."""
    if not is_valid_uuid(file_id):
        raise ValueError(f"Invalid File ID: {file_id}")
        
    matches = list(STORAGE_DIR.glob(f"{file_id}_*.pdf"))
    if not matches:
        raise FileNotFoundError(f"Output file not found: {file_id}")
    return matches[0]
