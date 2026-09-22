# Activate the RAG assistant

The backend is deployed on Render as `build`, at `https://kilsaran-rag.onrender.com`, and the GitHub Pages site is configured to use it. OpenAI API credit and the private assistant access code are required. Local `.env`, the indexing manifest, and `Build-access.private.txt` are ignored by Git. Unit tests simulate provider responses; all 480 source files were indexed and live answers were verified on 22 September 2026. The live checks covered silo water and hose guidance, ambiguous pallet questions, unpublished prices/delivery, and a nonexistent product. Rerun the evaluation after meaningful corpus or model changes.

## Architecture

GitHub Pages → authenticated Python backend → OpenAI vector-store search → OpenAI Responses → concise answer with source references.

OpenAI hosts the vector store and handles chunking, embeddings and semantic retrieval. The server retrieves up to 12 matches, includes up to eight passages in the LLM context, and requires citations on each returned claim. Citation validation checks that IDs correspond to retrieved passages; it does not prove that every statement is factually entailed. The initial retrieval threshold needs live evaluation. GPT-4.1 mini is the configurable initial answer model.

## 1. Index the corpus

Use an OpenAI API project with billing enabled. Supply `OPENAI_API_KEY` privately through an environment variable. Never paste it into chat, the website, source control, or browser connection settings.

```sh
.venv/bin/python scripts/index_vectors.py --upload
```

The importer prepares 480 files from the current corpus, preserving PDF page references. It saves resumable indexing progress to the ignored `data/vector-manifest.json` and prints `OPENAI_VECTOR_STORE_ID` only when all files are indexed. It uploads only the public Kilsaran corpus. Known scrambled troubleshooting tables are replaced with a direction to the original source. The existing corpus is not exhaustive and contains older sources.

For updated data, archive the local manifest and build a replacement store. Switch the backend only after the new store reports ready. Old stores/uploads are not automatically deleted; remove them after verification to avoid retaining unused resources. An interrupted upload before its ID is saved may leave an orphan file in the OpenAI project.

## 2. Host the backend

`Dockerfile` works on a container host. `render.yaml` provides an optional Render Blueprint using a **free instance**, matching the deployed service. It can take about a minute to wake after inactivity. No paid hosting has been provisioned.

Import `https://github.com/OctavianRo/kilsaran-service-companion` in the chosen host. Set these server environment variables using its secret settings:

- `OPENAI_API_KEY`: the OpenAI project key.
- `OPENAI_VECTOR_STORE_ID`: the completed store ID from step 1.
- `RAG_ACCESS_CODE`: a separate randomly generated access code, at least 32 characters. Share only with intended users.
- `ALLOWED_ORIGIN`: `https://octavianro.github.io`.
- `OPENAI_MODEL`: `gpt-4.1-mini` (or a tested compatible model).
- `DAILY_REQUEST_LIMIT`: `200` by default.

Use HTTPS. The container starts one Gunicorn worker with four threads. It limits authenticated traffic to 10 requests/minute and 200/day for that server process. These counters reset on restart and are not a billing cap. Keep a single replica, set provider spending controls, and use persistent limits/per-user authentication before wider distribution. CORS is not authentication; the separate access code is required for every chat call. The health endpoint reports configuration presence, not provider readiness.

## 3. Connect and evaluate

On the GitHub Pages site, choose **Assistant connection**, enter the HTTPS backend address and separate assistant access code. The access code stays in memory and must be re-entered after reloading. The backend URL alone is stored locally. The OpenAI key never goes to the browser.

In AI mode, questions and the last six conversation messages go to the backend and OpenAI. `store:false` is set for Responses; this is not a promise of zero provider retention. No application conversation database is created.

Check at least these real questions before using it on customer calls:

1. What water supply and hose does a mortar silo require? Must distinguish the published valve size from an undocumented hose diameter.
2. How much material is delivered and how much can the silo hold? Must not confuse material capacity with foundation load.
3. How many bags per pallet? Must ask which product when ambiguous.
4. The mixer is blocked; what should I do? Must refer safely to the full guide rather than inventing a procedure from scrambled columns.
5. What is the price and can it arrive tomorrow? Must not promise unpublished prices or availability.
6. Follow up “What about power?” after a silo question. Must preserve context and cite the right guide.
7. Ask about a nonexistent product. Must abstain.

Once verified, put only the public backend URL in `docs/config.json` as `ragApiUrl`, commit and push. Keep the access code and API key out of that file.

## Tests

```sh
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
node --test tests/search.test.cjs
```

Official references: [OpenAI Retrieval](https://developers.openai.com/api/docs/guides/retrieval), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
