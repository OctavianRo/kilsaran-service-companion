# Kilsaran Service Companion

**RAG upgrade:** OpenAI managed vector retrieval and a citation-checked answer backend are prepared. See [RAG_SETUP.md](RAG_SETUP.md) to activate it. The public website is AI-only and shows a setup message until the backend is configured; AI mode sends questions and recent conversation to the backend and OpenAI.

A local customer-service reference chatbot using **only kilsaran.ie** pages and linked PDFs. It retrieves original passages with source links and PDF page numbers. No AI account or API key is required. It is an independent internal reference, not an official Kilsaran application.

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

This reads Kilsaran's robots.txt, product/category/page sitemaps, and same-domain linked PDFs. Three workers fetch public sources; external links and external redirects are rejected. `ingest.py` without `--refresh` reuses the download cache. A complete run writes the snapshot atomically; the running app detects changes. The library screen reports source counts and failures. Network access is required only for indexing and opening source links (and optional web fonts).

## What answers mean

Answers are relevant **source extracts**, not generated technical advice. The search supports spelling variants such as “mortart”, product focus, and short follow-up questions. Each passage carries its original URL, plus PDF page when available. It does not claim to answer everything or confirm current stock, prices, delivery slots, unpublished hose fittings, or site-specific product suitability. For detailed procedures, open the full document and follow all safety instructions.

Coverage is all pages exposed in the product, category and general page sitemaps plus their directly linked, text-readable PDFs; not every possible website file, video, news article, or scanned document. Older brochures remain searchable and can conflict with newer documents; check dates and the current manufacturer guide before advising. It cannot recognise every unsupported premise: related search results are always explicitly labelled as extracts. No external AI service receives your questions.

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
