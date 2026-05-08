# Fact-Check Agent

Live URL: https://fact-check-1-vrdi.onrender.com/

Fact-Check Agent is an MVP for reviewing claims in PDF documents. Upload a PDF, choose Focused Scan for a smaller set of high-signal claims or Deep Scan for broader coverage, and the app returns an evidence-backed fact-check report.

## Features

- PDF upload and asynchronous job polling.
- Focused Scan and Deep Scan claim extraction modes.
- PDF text extraction with OpenRouter vision OCR fallback for pages where embedded text is unavailable.
- Tavily live web evidence gathering for current source material.
- OpenRouter-powered claim extraction and verdict synthesis.
- Verdict labels for Verified, Inaccurate, and False / Unsupported claims.
- Interactive results table with expandable reasoning, corrected facts, confidence, and source URLs.
- JSON report output from the backend job API.

## Local Backend

From Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OPENROUTER_API_KEY = "your-openrouter-api-key"
$env:TAVILY_API_KEY = "your-tavily-api-key"
$env:FRONTEND_ORIGIN = "http://localhost:5173"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend runs at `http://localhost:8000`.

Optional local limits:

```powershell
$env:OPENROUTER_MODEL = "openai/gpt-4o-mini"
$env:OPENROUTER_VISION_MODEL = "openai/gpt-4o-mini"
$env:MAX_CLAIMS_FOCUSED = "12"
$env:MAX_CLAIMS_DEEP = "25"
$env:MAX_OCR_PAGES = "5"
$env:MAX_PDF_SIZE_MB = "10"
```

## Local Frontend

In a second Windows PowerShell window:

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Smoke Test

Use the included sample PDF:

```text
sample_pdfs/trap_smoke_test.pdf
```

For a more realistic paragraph-style marketing brief, use:

```text
sample_pdfs/green_cloud_marketing_trap.pdf
```

Deployed smoke test:

1. Open https://fact-check-1-vrdi.onrender.com/.
2. Upload `sample_pdfs/trap_smoke_test.pdf`.
3. Choose `Focused`.
4. Click `Run fact-check`.
5. Confirm the report table appears with verdicts, confidence, source counts, and expandable evidence.
6. Expand at least one row and confirm reasoning plus source links are visible.
7. Click `JSON` and confirm the report downloads.

Expected sample behavior:

- The COVID-19 emergency end date, global population milestone, Apple $3 trillion milestone, and GPT-4 release date should generally be supported.
- The United States population claim of 500 million people in 2024 should be flagged as inaccurate or unsupported.
- The Eiffel Tower height claim of 10,000 meters should be flagged as false or unsupported.

Expected paragraph-brief traps:

- `Data centres consume 25 percent of all electricity worldwide` should be flagged as inaccurate.
- `Microsoft became carbon negative in 2020` should be flagged as inaccurate; it announced a 2030 goal in 2020.
- `The Paris Agreement was adopted in 2020` should be flagged as inaccurate; it was adopted in 2015.

## Render Deployment

This repo includes Render blueprint files for separate backend and frontend services in a monorepo layout:

- `backend/render.yaml` creates `fact-check-agent-api` with `rootDir: backend`, so `pip install -r requirements.txt` and `uvicorn app.main:app` run from the backend directory.
- `frontend/render.yaml` creates `fact-check-agent-web` with `rootDir: frontend`, so `npm install`, `npm run build`, and `staticPublishPath: dist` are relative to the frontend directory.

When using these blueprint files, create each Render service from its matching `render.yaml`. For manual setup instead, create the same two services and set the backend root directory to `backend` and the frontend root directory to `frontend`.

Deploy the backend first. Configure these Render environment variables:

- `OPENROUTER_API_KEY`: your OpenRouter API key.
- `TAVILY_API_KEY`: your Tavily API key.
- `FRONTEND_ORIGIN`: the deployed frontend URL, for example `https://fact-check-agent-web.onrender.com`.
- `OPENROUTER_MODEL`: `openai/gpt-4o-mini`.
- `OPENROUTER_VISION_MODEL`: `openai/gpt-4o-mini`.
- `MAX_CLAIMS_FOCUSED`: `12`.
- `MAX_CLAIMS_DEEP`: `25`.
- `MAX_OCR_PAGES`: `5`.
- `MAX_PDF_SIZE_MB`: `10`.
- `DEBUG_ERRORS`: `false` normally. Temporarily set to `true` while debugging provider/model failures, then redeploy the backend.

The backend build command is:

```bash
pip install -r requirements.txt
```

The backend start command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Deploy the frontend after the backend. Set `VITE_API_BASE_URL` to the deployed backend URL, for example `https://fact-check-agent-api.onrender.com`.

`VITE_API_BASE_URL` is baked into the Vite static bundle at build time. If the backend URL changes after deployment, update this environment variable and rebuild/redeploy the frontend.

The frontend build command is:

```bash
npm install && npm run build
```

The frontend static publish path is:

```text
dist
```

## MVP Runtime Note

Job polling currently uses an in-memory job store in the backend process. On Render, run the backend as a single process with one Uvicorn worker unless shared storage such as Redis, a database, or another durable queue is added. Multiple workers or instances would not share job state, so polling could miss jobs created by another process.

## Debugging Provider Failures

If the UI shows `Verification service failed. Please try again.`, first check the backend health endpoint:

```text
https://fact-check-dmer.onrender.com/api/health
```

If `configured` is `true`, enable temporary detailed errors:

1. In the backend Render service, set `DEBUG_ERRORS=true`.
2. Redeploy the backend.
3. Re-run the same PDF from the frontend.
4. The UI/job response will include the exception type and short provider message, such as an unsupported OpenRouter `response_format`, invalid model slug, rate limit, or Tavily error.
5. Set `DEBUG_ERRORS=false` again after debugging and redeploy.

Do not leave `DEBUG_ERRORS=true` for a public submission unless you are comfortable exposing short provider error messages to testers.
