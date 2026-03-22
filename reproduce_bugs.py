import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("/mnt/T7/PythonWorkspace/02_deneme_projeleri/pdf_regulator")
sys.path.append(str(PROJECT_ROOT.absolute()))

from backend.services import pdf_service
import fitz

def test_extract_ordering():
    print("--- Testing Page Ordering ---")
    pdf_id = "719a825b5857443bac1269a72fd06fbe"
    # Try to extract pages in reverse order: [2, 1, 0]
    page_indices = [2, 1, 0]
    try:
        file_id, filename = pdf_service.extract_pages(pdf_id, page_indices)
        out_path = pdf_service.get_output_path(file_id)
        
        # Verify order by comparing text content if possible, 
        # or just checking if we can get the pages in that order.
        src_path = PROJECT_ROOT / f"backend/storage/{pdf_id}_src.pdf"
        src_doc = fitz.open(str(src_path))
        out_doc = fitz.open(str(out_path))
        
        print(f"Extracted {len(out_doc)} pages")
        
        match = True
        for i, original_idx in enumerate(page_indices):
             src_text = src_doc[original_idx].get_text().strip()[:20]
             out_text = out_doc[i].get_text().strip()[:20]
             if src_text != out_text:
                  print(f"FAILURE: Page {i} (original {original_idx}) does not match!")
                  print(f"  Expected start: {src_text!r}")
                  print(f"  Got start:      {out_text!r}")
                  match = False
                  break
        
        if match:
             print("SUCCESS: Page order is preserved.")
             
        out_doc.close()
        src_doc.close()
    except Exception as e:
        print(f"Order test failed: {e}")

def test_duplicate_pages_content():
    print("\n--- Testing Duplicate Pages Content ---")
    pdf_id = "719a825b5857443bac1269a72fd06fbe"
    page_indices = [0, 0]
    try:
        file_id, filename = pdf_service.extract_pages(pdf_id, page_indices)
        out_path = pdf_service.get_output_path(file_id)
        out_doc = fitz.open(str(out_path))
        
        text0 = out_doc[0].get_text().strip()[:20]
        text1 = out_doc[1].get_text().strip()[:20]
        
        if text0 == text1 and len(out_doc) == 2:
            print("SUCCESS: Duplicate pages have identical content and correct count.")
        else:
            print(f"FAILURE: Duplicate pages mismatch or wrong count ({len(out_doc)}).")
        out_doc.close()
    except Exception as e:
        print(f"Duplicate content test failed: {e}")

if __name__ == "__main__":
    test_pdf = PROJECT_ROOT / "backend/storage/719a825b5857443bac1269a72fd06fbe_src.pdf"
    if not test_pdf.exists():
        print(f"Test PDF not found at {test_pdf}.")
    else:
        test_extract_ordering()
        test_duplicate_pages_content()
