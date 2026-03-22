import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("/mnt/T7/PythonWorkspace/02_deneme_projeleri/pdf_regulator")
sys.path.append(str(PROJECT_ROOT.absolute()))

from backend.services import pdf_service

def test_file_id_prefix_bug():
    print("--- Testing File ID Prefix Bug ---")
    STORAGE_DIR = pdf_service.STORAGE_DIR
    
    # Create two files where one file_id is a prefix of another
    id1 = "testabc"
    id2 = "testa"
    
    f1 = STORAGE_DIR / f"{id1}_file1.pdf"
    f2 = STORAGE_DIR / f"{id2}_file2.pdf"
    
    f1.write_text("dummy pdf 1")
    f2.write_text("dummy pdf 2")
    
    try:
        # Looking for id2 ("testa") might match id1 ("testabc") if we're not careful
        # Current glob is f"{file_id}_*.pdf"
        path = pdf_service.get_output_path(id2)
        print(f"Requested {id2}, got {path.name}")
        
        # Now what if id1 is requested?
        path1 = pdf_service.get_output_path(id1)
        print(f"Requested {id1}, got {path1.name}")
        
    finally:
        if f1.exists(): f1.unlink()
        if f2.exists(): f2.unlink()

if __name__ == "__main__":
    test_file_id_prefix_bug()
