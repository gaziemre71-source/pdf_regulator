# PDF Selector & Rotator

PDF sayfalarını seçip çıkarabilen ve döndürebilen hafif web uygulaması.

## Tech Stack

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.12 · FastAPI · Uvicorn |
| PDF İşleme | PyMuPDF (fitz) |
| Frontend | HTMX · TailwindCSS CDN |
| Template | Jinja2 |

## Kurulum

```bash
cd /mnt/T7/PythonWorkspace/02_deneme_projeleri/PDFSELECTOR
.venv/bin/pip install -r requirements.txt
```

## Çalıştırma

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Tarayıcıda: [http://localhost:8000](http://localhost:8000)

## API Endpoint'leri

| Method | URL | Açıklama |
|---|---|---|
| `POST` | `/upload` | PDF yükle |
| `GET` | `/page/{pdf_id}/{page_num}` | Sayfa PNG'si |
| `POST` | `/extract` | Sayfa aralığını çıkar |
| `POST` | `/rotate` | Sayfa aralığını döndür |
| `GET` | `/download/{file_id}` | PDF indir |

## Dizin Yapısı

```
PDFSELECTOR/
├─ backend/
│   ├─ main.py
│   ├─ routers/  (upload, pages, extract, rotate, download)
│   ├─ services/ (pdf_service.py)
│   └─ storage/  (geçici dosyalar)
├─ frontend/
│   ├─ templates/ (index.html, partials/)
│   └─ static/css/ (app.css)
├─ requirements.txt
└─ .venv/
```
