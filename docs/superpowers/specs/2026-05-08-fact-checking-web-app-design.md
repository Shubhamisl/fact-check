# Fact-Checking Web App Design

Date: 2026-05-08

## Objective

Build a deployed web app that lets users upload a PDF and receive an automated fact-checking report. The app acts as a truth layer for marketing or business content by extracting concrete claims, checking them against live web evidence, and flagging claims as verified, inaccurate, or false/unsupported.

The final app must be live on Render and testable with evaluator-provided PDFs.

## Product Direction

The interface should feel like a polished analyst workbench, not a marketing landing page. The first screen is the usable application: upload a PDF, choose scan mode, run the check, and inspect results.

The UI should be dense, clear, and trustworthy:

- Compact top bar with app name and run/config status.
- Left control panel for upload, scan mode, and run controls.
- Main workspace for the verdict table.
- Expandable detail drawer or row expansion for evidence and reasoning.
- Calm visual system with restrained verdict colors.
- Clear empty, loading, error, and completed states.
- No hero section, decorative gradients, or promotional copy.

## Platform

Use Render with a React frontend and FastAPI backend.

Render is preferred because this app needs PDF processing, several live searches, and LLM synthesis. Those tasks are easier to run reliably in a normal backend service than in short serverless functions.

## External Services

Use:

- OpenRouter for claim extraction, OCR fallback, and verdict synthesis.
- Tavily for live web search and evidence gathering.

Required environment variables:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_VISION_MODEL`
- `TAVILY_API_KEY`

Optional environment variables:

- `MAX_CLAIMS_FOCUSED`
- `MAX_CLAIMS_DEEP`
- `MAX_OCR_PAGES`
- `MAX_PDF_SIZE_MB`
- `TAVILY_SEARCH_DEPTH`

## Scan Modes

The app supports two scan modes.

Focused mode is the default. It extracts concrete claims that are most likely to matter in a trap document:

- Statistics
- Dates
- Percentages
- Counts
- Money and financial figures
- Market sizes
- Technical figures
- Rankings
- Named factual claims with measurable details

Deep Scan mode broadens extraction to more general factual claims. It may catch more issues, but it is slower and more likely to produce noisy or low-confidence checks.

Default limits:

- Focused mode: up to 12 claims.
- Deep Scan mode: up to 25 claims.
- Adaptive follow-up: up to 1 extra Tavily search for weak, contradictory, or high-impact claims.
- PDF size cap: 10 MB unless configured otherwise.

## Backend Architecture

The backend is a modular FastAPI service.

Modules:

- `pdf_service`: accepts uploaded PDFs, extracts text and metadata, and tracks page numbers.
- `ocr_service`: renders pages with little or no extractable text and sends page images to a vision-capable OpenRouter model for OCR.
- `claim_extractor`: asks OpenRouter to extract structured claims according to the selected scan mode.
- `claim_grouper`: groups related claims by topic so searches can reuse evidence.
- `search_service`: calls Tavily and normalizes evidence into title, URL, snippet/content, published date when available, and source type hints.
- `verifier`: asks OpenRouter to evaluate each claim using only gathered evidence.
- `orchestrator`: coordinates the run, enforces limits, and decides whether an adaptive follow-up search is needed.

## Processing Flow

1. User uploads a PDF and chooses Focused or Deep Scan.
2. Backend validates file type and size.
3. Backend extracts text page by page.
4. Pages with poor text extraction are rendered to images and processed through OpenRouter vision OCR, up to the configured OCR limit.
5. Extracted and OCR text are merged with page references.
6. OpenRouter extracts structured claims.
7. Claims are grouped by topic.
8. Tavily searches gather live evidence for each group and important individual claims.
9. OpenRouter verifies each claim against the collected evidence.
10. For weak, contradictory, or high-impact claims, the orchestrator performs one adaptive follow-up Tavily search and reruns verification for that claim.
11. Backend returns a structured report.
12. Frontend renders the interactive report and exposes a JSON download.

## Verdicts

The public verdict categories are:

- `Verified`: credible live evidence supports the claim closely.
- `Inaccurate`: the topic is real, but the specific number, date, amount, or technical detail is wrong or outdated. The report must provide the corrected fact when available.
- `False / Unsupported`: no credible evidence supports the claim, or evidence contradicts its core assertion.

Internally, the verifier may identify a weak-evidence state, but the UI maps that to `False / Unsupported` with low confidence and clear reasoning.

Each claim result includes:

- Original claim text.
- Page number when available.
- Claim type.
- Verdict.
- Corrected fact when available.
- Confidence: High, Medium, or Low.
- Reasoning.
- Evidence sources with URLs.
- Search queries used.

## Trust And Evidence Rules

The verifier must be evidence-grounded:

- It may only verify claims using Tavily evidence supplied in the prompt.
- It must not rely on model memory for final verdicts.
- Every verified or inaccurate verdict should cite at least one source URL.
- Unsupported claims should explain what evidence was missing or contradictory.
- Conflicting evidence should be surfaced, with preference given to recent authoritative sources.
- Corrected facts must be separated from the original extracted claim.

## API Design

Phase 1 uses a synchronous MVP endpoint:

- `POST /api/fact-check`
  - Input: multipart PDF upload, scan mode.
  - Output: complete fact-check report JSON.

Supporting endpoints:

- `GET /api/health`
  - Reports service status and whether required configuration is present.

Phase 2 adds job polling after the core pipeline works:

- `POST /api/jobs`
  - Starts a fact-check run and returns a job ID.
- `GET /api/jobs/{id}`
  - Returns status, progress message, partial results if available, and final report when complete.

Job polling is planned, but it should not block the first working deployment.

## Frontend Behavior

The frontend renders:

- PDF upload control.
- Focused / Deep Scan segmented control.
- Run button.
- Progress area with stages such as extracting text, reading scanned pages, extracting claims, searching evidence, and finalizing verdicts.
- Verdict summary counts.
- Results table with verdict badge, claim, corrected fact, confidence, and source count.
- Expandable detail view for each claim.
- JSON download button after completion.
- Error states for bad file type, large file, missing backend config, API failure, and no extractable text.

## Error Handling

Expected failures should be explicit and recoverable:

- Non-PDF file: reject with a clear message.
- Oversized PDF: reject with configured limit.
- No extractable text and OCR unavailable or exhausted: report that text could not be extracted.
- Missing OpenRouter or Tavily key: health check and API response identify configuration problem.
- Tavily failure: affected claims show verification unavailable rather than fabricated verdicts.
- OpenRouter failure: show a run-level error or claim-level failure depending on where it occurs.
- Timeout risk: keep claim and OCR limits bounded in Phase 1.

## Testing

Testing should focus on assignment success:

- PDF extraction works for normal text PDFs.
- OCR fallback is called only for pages with little or no text.
- Claim extraction returns schema-valid claims.
- Search results are normalized consistently.
- Verifier returns schema-valid verdicts.
- Pipeline can be tested with mocked OpenRouter and Tavily responses.
- A sample trap PDF contains known true, false, and outdated claims.
- Frontend smoke test covers upload, progress, verdict table rendering, detail expansion, and JSON download.

## Deployment

Render deployment includes:

- FastAPI backend service.
- React frontend static site or web service.
- Environment variables configured in Render.
- README instructions for local setup and Render deployment.
- A live Render URL included after deployment.

## Acceptance Criteria

The app is successful when:

- A user can visit the live Render URL.
- A user can upload their own PDF.
- The app extracts concrete factual claims from the PDF.
- The app searches live web evidence through Tavily.
- The report flags claims as Verified, Inaccurate, or False / Unsupported.
- Inaccurate claims include corrected facts when available.
- Results include source URLs.
- The report is visible in the app and downloadable as JSON.
- The app can catch intentional lies and outdated statistics in a trap document.
