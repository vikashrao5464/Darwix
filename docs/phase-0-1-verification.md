# Phase 0 and 1 verification

Verified on 2026-10-01 in the supplied Windows workspace. Only Phases 0 and 1 are implemented; Q1 voice, Q3 localization and Q4 real-time behavior remain future work.

| Check | Actual result / evidence |
|---|---|
| Backend tests | **56 passed**, one upstream Starlette warning about its legacy `httpx` TestClient integration; exit 0. [JUnit output](../evaluations/phase-0-1-tests.xml). |
| Dependency consistency | `python -m pip check`: no broken requirements. |
| Environment template | `.env.example` parsed successfully; the configured government-ID redaction regexes worked and providers defaulted to hash/extractive. |
| Frontend production build | `npm --prefix frontend run build`: passed; Vite 7.3.6 built the React bundle. |
| Default vector service | Docker Qdrant 1.19.1 started from the pinned image digest. Collection alias created and 23 records inserted/read. |
| Full rebuild | Eight successful synthetic sources, 23 chunks, one exact duplicate skipped, one near duplicate flagged/retained. Actual ingestion report is generated under ignored `data/normalized/`. |
| Retrieval evaluation | **10 correct, 1 incorrect** out of 11; exit 1 intentionally signals the documented paperwork paraphrase miss. [Full results](../evaluations/retrieval/results.json). |
| Real backend HTTP | `GET http://127.0.0.1:8000/health` returned `{"status":"ok"}`. Document question returned the bank-statement/registration requirements with `demo_faq.html` citation. |
| Unavailable Qdrant CLI | Pointed ingestion at a non-listening loopback port; it exited 1 with `qdrant_unavailable`, a manual recovery action and only the exception class in JSON logs. No provider traceback/body was printed. |
| Frontend route serving | `/call` and `/live` returned HTTP 200 from the running Vite server. |
| Browser smoke | Headless installed Chrome loaded `/call`, observed the backend connection, submitted a document question and checked answer/citation, submitted an unknown lunar-tourism question and checked the human-assistance fallback, and loaded the Phase 4 placeholder. No browser page errors. Temporary smoke tooling is in ignored `data/state/browser-tools/`, outside the source/dependency manifests. |
| Manual provenance review | Twelve actual chunks inspected: [review notes](chunk-review.md). |

Reproduce the maintained checks from the root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/phase-0-1-tests.xml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/ingest.py --rebuild
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py
```

The test suite verifies all seven SQLite tables and sample insert/read, foreign keys, empty index, unsupported FAQ, product/language filtering, provider timeout cancellation, provider exceptions without secret/PII logs, corrupt/empty/unsupported source handling, PII true positives and preserved business numbers, chunk boundaries/metadata, duplicate suppression, hosted adapter request contracts with mocks, version replacement, failed staging/rebuild preservation and explicit reporting when an index publishes but its snapshot export fails.

The pinned environment was tested on Python 3.14.3 and Node 22.20.0. Hosted OpenAI/secured remote Qdrant were not called with real credentials. The evidence is a small synthetic benchmark and does not establish production retrieval quality. No voice recordings, regional-accent tests or measured call P50/P95 are claimed.

An existing service on IPv6 `localhost:8000` returned 404 for the first localhost smoke request. The Darwix server on IPv4 `127.0.0.1:8000` returned the expected health/API responses. Browser configuration and documented commands use explicit IPv4; unrelated listeners were left untouched.

Manual actions are listed in [README](../README.md): start Docker/processes, optionally configure a hosted account, review approved real sources before replacing synthetic content, and stop the backend before opening an embedded Qdrant store from CLI tools.
