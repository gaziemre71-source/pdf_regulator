import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("/mnt/T7/PythonWorkspace/02_deneme_projeleri/pdf_regulator")
sys.path.append(str(PROJECT_ROOT.absolute()))

from backend.services import pdf_service

def test_wildcard_glob():
    print("--- Testing Wildcard in get_output_path ---")
    try:
        # STORAGE_DIR.glob("*_*.pdf") will match everything in storage
        # and get_output_path returns the first match.
        path = pdf_service.get_output_path("*")
        print(f"Wildcard '*' matched: {path.name}")
    except Exception as e:
        print(f"Wildcard test: {e}")

def test_traversal_src_path():
    print("\n--- Testing Path Traversal in _src_path ---")
    # _src_path: STORAGE_DIR / f"{pdf_id}_src.pdf"
    # If we pass pdf_id="../../README.md", it looks for STORAGE_DIR / "../../README.md_src.pdf"
    # This might not find README.md directly, but what if we pass pdf_id="."?
    # STORAGE_DIR / "._src.pdf"
    
    # Let's try to bypass the suffix.
    # In some systems, a null byte \0 or similar could truncate, but not in Path.
    
    # However, if we can control the filename...
    # The service doesn't validate if pdf_id is a hex uuid.
    
    pass

if __name__ == "__main__":
    test_wildcard_glob()
