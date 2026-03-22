import sys
import os
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path("/mnt/T7/PythonWorkspace/02_deneme_projeleri/pdf_regulator")
sys.path.append(str(PROJECT_ROOT.absolute()))

from backend.services import preprocessor

def test_fake_pdf():
    print("--- Testing Fake PDF Extension ---")
    fake_content = b"this is completely garbage text not a pdf or image"
    try:
        preprocessor.preprocess_to_pdf(fake_content, "fake_doc.pdf")
        print("FAIL: Preprocessor accepted a fake PDF!")
    except Exception as e:
        print(f"SUCCESS: Preprocessor blocked fake PDF -> {e}")

def test_valid_pdf():
    print("--- Testing Actual PDF Header ---")
    # minimal valid pdf header
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    try:
        res, fn = preprocessor.preprocess_to_pdf(pdf_content, "valid_header.pdf")
        print(f"SUCCESS: Preprocessor accepted valid PDF header -> {fn}")
    except Exception as e:
        print(f"FAIL/EXPECTED: Preprocessor threw -> {e} (Expected exception from fitz if object is incomplete)")

if __name__ == "__main__":
    test_fake_pdf()
    test_valid_pdf()
