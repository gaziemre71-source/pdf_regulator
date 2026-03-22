import fitz
import os
from pathlib import Path

def preprocess_to_pdf(content: bytes, original_filename: str) -> tuple[bytes, str]:
    """
    Magic bytes üzerinden dosyanın türünü tespit eder.
    Eğer resim dosyasıysa fitz aracılığıyla PDF'e dönüştürür.
    Zaten PDF ise doğruluğunu teyit edip bytes döner.
    
    Desteklenmeyen veya bozuksa ValueError fırlatır.
    
    Returns:
        (pdf_bytes, final_filename)
    """
    if len(content) < 4:
        raise ValueError("Desteklenmeyen veya bozuk dosya formatı. Lütfen .pdf, .tiff, .jpeg, .jpg veya .png yükleyiniz.")
        
    # Magic Bytes Check
    if content.startswith(b"%PDF-"):
        filetype = "pdf"
    elif content.startswith(b"\xff\xd8"):
        filetype = "jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        filetype = "png"
    elif content.startswith(b"II*\x00") or content.startswith(b"MM\x00*"):
        filetype = "tiff"
    else:
        raise ValueError("Desteklenmeyen veya bozuk dosya formatı. Lütfen .pdf, .tiff, .jpeg, .jpg veya .png yükleyiniz.")
        
    base_name = os.path.splitext(original_filename)[0]
    final_filename = f"{base_name}.pdf"
    
    if filetype == "pdf":
        try:
            # Sadece bozuk olup olmadığını anlamak için parse et
            doc = fitz.open("pdf", content)
            doc.close()
            return content, final_filename
        except Exception:
            raise ValueError("Bozuk PDF dosyası. Lütfen geçerli bir belge yükleyiniz.")
            
    # Görsel dosya, pdf'e çevir
    try:
        doc = fitz.open(stream=content, filetype=filetype)
        pdf_bytes = doc.convert_to_pdf()
        doc.close()
        return pdf_bytes, final_filename
    except Exception as e:
        raise ValueError(f"Görsel pdf'e çevrilemedi: {e}")
