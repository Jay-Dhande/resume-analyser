# Project Context

## Purpose and Stack

Resume Analyzer accepts resume data or PDFs, produces resume analysis, parses job descriptions into requirements, and compares resumes with job requirements. The implementation uses Python, FastAPI, Pydantic, Google's `google-genai` client for Gemini, `pypdf` for PDF text extraction, and pytest. Imports and the active environment verify these technologies; no dependency manifest is tracked, so dependency versions are not reproducibly declared.

## Repository Map

- `main.py`: FastAPI application, request models, service construction, endpoints, and HTTP error translation.
- `models/resume.py`: `Resume`, `Education`, and `Experience` Pydantic models.
- `models/job.py`: `JobDescription` input model and `JobRequirements` extracted from job descriptions.
- `models/job_match.py`: `JobMatch` response fields for skill and experience matches plus summary.
- `models/analysis.py`: `Finding` and `ResumeAnalysis` response models.
- `models/suggestions.py`: `ImprovementSuggestion` and `ResumeSuggestions` response models.
- `services/llm_service.py`: Gemini prompts and conversion of model responses into Pydantic models.
- `services/pdf_service.py`: extraction of text from PDF pages with `pypdf`.
- `services/deterministic_analyzer.py`: deterministic resume completeness, date, duplicate-skill, and formatting checks.
- `services/job_matcher.py`: deterministic required/preferred skill and experience matching.
- `tests/`: deterministic analyzer, job matcher, and endpoint tests.
- `test_pdf.py`: standalone PDF extraction script; it prints extracted text and does not define pytest test functions.
- `manual_resume_parser.py`: standalone PDF-to-Gemini parsing script; invoking it requires Gemini configuration and makes a provider call.
- `AGENTS.md`: coding-agent workflow and repository constraints.

## API and Data Flow

- `GET /health`: returns `{"status": "ok"}`.
- `POST /chat`: accepts `ChatRequest { prompt: str }`, calls `LLMService.generate`, and returns `{"response": str}`.
- `POST /resume/parse`: accepts an uploaded PDF; `PDFService` extracts text, then `LLMService.parse_resume` returns `Resume`. Gemini `ServerError` is translated to HTTP 503 with a generic message.
- `POST /resume/analyze`: accepts a `Resume`; Gemini returns `ResumeAnalysis`, then deterministic findings are appended to selected categories. The response model is `ResumeAnalysis`.
- `POST /resume/match`: accepts `ResumeMatchRequest { resume: Resume, job: JobRequirements }`; invokes `JobMatcher.match` and returns `JobMatch` without Gemini.
- `POST /resume/match-job`: accepts `ResumeJobMatchRequest { resume: Resume, job_description: str }`; parses the description into `JobRequirements` with Gemini, then runs deterministic matching and returns `JobMatch`. Gemini `ServerError` becomes HTTP 503 with a generic message.
- `POST /resume/suggestions`: accepts `ResumeSuggestionsRequest { resume: Resume, analysis: ResumeAnalysis, job_match: JobMatch }`; asks Gemini for grounded suggestions using those inputs and returns `{ "suggestions": [...] }` with category, priority, issue, evidence, and recommendation. Results are ordered by missing required skill, missing required experience, then resume quality. Gemini `ServerError` becomes HTTP 503 with a generic message.
- `POST /job/parse`: accepts `JobDescriptionRequest { title?: str, description: str }`; parses the description into and returns `JobRequirements`. The current route passes only `description` to the LLM service; `title` is unused.

FastAPI/Pydantic validate JSON request bodies; invalid bodies receive the framework's HTTP 422 response. `JobRequirements` contains required/preferred skills and experience lists. `JobMatch` contains matched/missing required and preferred skills and experience, matching experience descriptions, and a summary.

## Service Responsibilities

- `LLMService` creates the Gemini client from `GEMINI_API_KEY` and reads `GEMINI_MODEL`. It implements free-text generation, resume parsing, resume analysis, and job-requirement extraction. Resume parsing retries Gemini server failures up to three attempts with exponential waits; job parsing and analysis do not currently retry.
- `LLMService.suggest_improvements` generates Pydantic-validated suggestions from the supplied resume, analysis, and match; its prompt requires supported evidence and forbids invented candidate claims or metrics.
- `PDFService` joins extracted text from all PDF pages.
- `DeterministicAnalyzer` checks missing contact details/sections, education date ordering, duplicate skills, and selected PDF extraction artifacts.
- `JobMatcher` compares normalized skills (with a small hard-coded alias map) and uses keyword overlap for experience requirements. Matching itself does not call Gemini.

## Tests and Latest Verification

Tests currently cover three deterministic-analyzer behaviors, seven matcher behaviors, three `/resume/match-job` endpoint behaviors, and three `/resume/suggestions` endpoint behaviors. Endpoint tests monkeypatch LLM service calls, so they do not call Gemini. Latest verified command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -p no:cacheprovider
16 passed, 2 warnings
```

The warnings are from Starlette's `httpx` TestClient integration and a deprecated alias used by `google-genai`. The run reported 16 test items across `tests/` and did not report a separate test item for root `test_pdf.py`. Python AST syntax validation passed for `services/llm_service.py`, and Pylance currently reports no errors in that file.

## Known Limitations and Technical Debt

- In `/resume/analyze`, `DeterministicAnalyzer` can produce `Contact` and `Dates` findings, but `main.py` only appends findings in the `Completeness`, `Experience`, `Skills`, `Projects`, `Formatting`, and `ATS` categories. Contact and date findings are therefore currently dropped from the response.
- Experience matching is heuristic keyword overlap, not semantic matching. Skill alias coverage is limited to the aliases hard-coded in `JobMatcher`.
- The PDF resume parse, raw-description match, and resume suggestions routes translate Gemini `ServerError` into HTTP 503. Other Gemini-using routes do not currently provide that translation; job parsing and suggestion generation do not retry.
- Resume improvement suggestions are prompt-grounded and response-validated, but the factual correctness of free-text evidence and recommendations still depends on Gemini following the instructions; current tests mock the LLM response and do not evaluate provider-generated output.
- `JobDescriptionRequest.title` is accepted but unused by `/job/parse`.
- There is no tracked `requirements.txt`, `pyproject.toml`, or other dependency lock/manifest. A fresh environment cannot reproduce installed dependency versions from tracked project files alone.
- `main.py` has duplicate `FastAPI` imports and imports `JobDescription` without using it. These are cleanup items, not behavior changes.
- `manual_resume_parser.py` performs PDF extraction and a live Gemini request when run; it should not be included in API-free automated tests.

## Design Decisions and Constraints

- Keep resume and job data in Pydantic models at API boundaries.
- Use Gemini for extracting structured content and generating analysis, but keep resume/job matching deterministic.
- Reuse existing models and services; preserve existing endpoint request/response contracts unless a feature requires otherwise.
- Tests should mock Gemini calls and must not use external LLM APIs unless explicitly requested.
- Do not expose secrets or edit `.env`; do not commit generated files or `__pycache__` artifacts. `.gitignore` currently ignores `.env` and PDFs, but not Python bytecode.
- No database, authentication, frontend, embeddings, RAG, or additional frameworks are present in the inspected application.

## Milestones and Next Steps

Current verified capabilities include PDF resume parsing, LLM-backed resume analysis plus deterministic checks, job requirement extraction, structured deterministic matching, the end-to-end `/resume/match-job` route, and `/resume/suggestions` with typed output, required-gap-first ordering, and mocked endpoint tests.

Prioritized follow-up work:

1. Preserve `Contact` and `Dates` deterministic findings in `/resume/analyze`, with focused tests.
2. Add a dependency manifest and a clean-environment setup path so installs and supported versions are reproducible.
3. Add focused route/service tests for existing error handling and `/job/parse` behavior without live Gemini calls.
4. Review the experience matching heuristic and expand alias coverage only when supported by explicit product requirements and tests.

## Running the Application and Tests

The application reads `GEMINI_API_KEY` and `GEMINI_MODEL` during service initialization; configure them in the local environment or `.env` without committing secrets. From the repository root, with the project dependencies installed and virtual environment activated:

```powershell
python -m uvicorn main:app --reload
$env:PYTHONPATH = "."
python -m pytest
```

`PYTHONPATH=.` was required for pytest in the verified Git Bash environment. The equivalent Git Bash test command is `PYTHONPATH=. pytest`. The active environment verified Uvicorn 0.53.0 on CPython 3.14.7; these are environment observations, not pinned project requirements.