import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any

# Geçiçi veri tabanının aynı yerlerde durması için storage dizinini bulalım
STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
DB_PATH = STORAGE_DIR / "tasks.db"

# Thread-local storage for sqlite connections since same-thread connections are safer.
_local = threading.local()

def get_db_connection():
    """Mevcut thread için veritabanı bağlantısı döner."""
    if not hasattr(_local, "conn"):
        # check_same_thread=False allows sharing but thread-local is safer for sqlite.
        # It's okay to just use thread-locals for Fastapi's sync endpoints or asyncio threadpool.
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn

def init_db():
    """Tüm tabloları ve gereken başlangıç durumunu oluşturur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            pdf_id TEXT,
            page_count INTEGER,
            filename TEXT,
            label TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

def cleanup_orphan_tasks():
    """Sunucu yeniden başladığında 'processing' durumunda kalan asılı görevleri temizler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE ocr_tasks 
        SET status = 'failed', error_message = 'Sunucu beklenmeyen bir şekilde yeniden başlatıldı.' 
        WHERE status = 'processing'
    ''')
    conn.commit()

def create_task(task_id: str, filename: str, label: str = ""):
    """Yeni bir OCR işlemi oluşturur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ocr_tasks (task_id, status, filename, label) VALUES (?, 'processing', ?, ?)", 
        (task_id, filename, label)
    )
    conn.commit()

def update_task_success(task_id: str, pdf_id: str, page_count: int, filename: str):
    """Görev başarılı olduğunda durumunu günceller."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE ocr_tasks 
        SET status = 'done', pdf_id = ?, page_count = ?, filename = ?
        WHERE task_id = ?
    ''', (pdf_id, page_count, filename, task_id))
    conn.commit()

def update_task_failure(task_id: str, error_message: str):
    """Görev başarısız olduğunda durumunu günceller."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE ocr_tasks 
        SET status = 'failed', error_message = ?
        WHERE task_id = ?
    ''', (error_message, task_id))
    conn.commit()

def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Görevin mevcut durumunu döner."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ocr_tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None

