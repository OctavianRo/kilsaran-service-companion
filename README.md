# Build Service Companion

**Live deployment:** [Build](https://octavianro.github.io/kilsaran-service-companion/) uses the hosted OpenAI RAG backend at `https://kilsaran-rag.onrender.com`. The Render service is named `build` and uses free hosting. API credit and the private assistant access code are required. See [RAG_SETUP.md](RAG_SETUP.md) for maintenance instructions.

A local customer-service reference chatbot using **kilsaran.ie** pages and its officially linked PDFs. It retrieves original passages with source links and PDF page numbers. No AI account or API key is required. It is an independent internal reference, not an official Kilsaran application.

## Run

Double-click `start.command`, or run:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open http://localhost:8765. The server is bound to your computer only. Conversations are kept in browser memory and clear when you reload or start a new conversation.

## Refresh the website library

```sh
.venv/bin/python ingest.py --refresh
```

This reads Kilsaran's robots.txt, product/category/page sitemaps, and linked PDFs, including extensionless downloads from Kilsaran’s dedicated `g13660.ideagenqpulse.com` document-service tenant. Three workers fetch public sources; unrelated external links and redirects are rejected. The technical library is always included. Document links are deduplicated by document ID and retain product/plant associations. `ingest.py` without `--refresh` reuses the download cache. A complete run writes the snapshot atomically; the running app detects changes. The library screen reports source counts and failures. Network access is required only for indexing and opening source links (and optional web fonts).

## What answers mean

Answers are relevant **source extracts**, not generated technical advice. The search supports spelling variants such as “mortart”, product focus, and short follow-up questions. Each passage carries its original URL, plus PDF page when available. It does not claim to answer everything or confirm current stock, prices, delivery slots, unpublished hose fittings, or site-specific product suitability. For detailed procedures, open the full document and follow all safety instructions.

Coverage is all pages exposed in the product, category and general page sitemaps plus their linked PDFs and all document links exposed in the technical library. Optional local OCR reads scanned pages; unavailable files and weak pages are reported explicitly. This does not cover every possible unlinked file, video or news article. Older brochures remain searchable and can conflict with newer documents; check dates and the current manufacturer guide before advising. It cannot recognise every unsupported premise: related search results are always explicitly labelled as extracts. No external AI service receives your questions.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## GitHub Pages (access from work)

The AI-only website lives in `docs/`. GitHub serves its interface; answers require the configured RAG backend. Questions and recent conversation are sent to the backend and OpenAI. No browser extract matcher or full corpus is shipped to the website. Without a connection, it shows a setup message. See RAG_SETUP.md for activation. The older local reference tool is separate from the public site.

After updating the source library, rebuild and test before publishing:

```sh
.venv/bin/python ingest.py --refresh
python3 scripts/build_pages.py
node --test tests/search.test.cjs
```

Commit and push the updated `docs/` folder. GitHub Pages publishes from `main` → `/docs`. Website questions use the managed vector retrieval and LLM backend exclusively. No automatic refresh schedule is configured.

## Complete technical-library refresh

Compile `scripts/ocr_pdf.swift` with `swiftc` on macOS, then set `PDF_OCR_COMMAND` to that executable when running `ingest.py`. OCR runs locally and is cached by PDF content hash. Inspect `data/document-audit.md` for coverage and remaining failures.

`scripts/refresh_vectors.py` builds a separate replacement store with resumable parallel uploads and batch attachments. Its manifest lives in ignored `data/cache/replacement-vector-manifest.json`. Verify retrieval and answers before changing the hosted backend’s vector-store setting. Retain the old store for rollback. Refreshing the local JSON or Pages metadata alone does **not** update live RAG.
