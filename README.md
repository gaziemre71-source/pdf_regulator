---
title: PDF Regulator
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# PDF Regulator

Professional PDF tool to extract, rotate, and optimize pages with advanced text recognition (OCR) and cleanup.

## Features
- Upload PDF, TIFF, JPEG, PNG files
- Page preview grid with drag-and-drop reordering
- Select and extract pages into a new PDF
- Rotate pages individually
- OCR processing via `ocrmypdf` (Turkish + English)

## Local Development

```bash
python -m uvicorn backend.main:app --reload
```
