# ── Stage 1: base system image ────────────────────────────────────────────────
FROM python:3.11-slim

# HuggingFace Spaces runs the container as a non-root user (UID 1000).
# We create that user here so file permissions are consistent.
RUN useradd -m -u 1000 appuser

# ── System dependencies ────────────────────────────────────────────────────────
# ocrmypdf requires Tesseract OCR + language packs + Ghostscript
RUN apt-get update && apt-get install -y --no-install-recommends \
    ocrmypdf \
    tesseract-ocr \
    tesseract-ocr-tur \
    tesseract-ocr-eng \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────────
COPY . .

# Storage dir must be writable by appuser at runtime
RUN mkdir -p backend/storage && chown -R appuser:appuser /app

USER appuser

# ── HuggingFace Spaces expects port 7860 ──────────────────────────────────────
ENV PORT=7860
EXPOSE 7860

# ── Entrypoint ─────────────────────────────────────────────────────────────────
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
