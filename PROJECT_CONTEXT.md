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
- `models/resume_job_analysis.py`: aggregate `ResumeJobAnalysisResponse` returned by the end-to-end workflow.
- `models/ats_score.py`: structured overall score, category points, requirements, uncertainty, and compatibility checks.
- `services/llm_service.py`: Gemini prompts and conversion of model responses into Pydantic models.
- `services/pdf_service.py`: extraction of text from PDF pages with `pypdf`.
- `services/deterministic_analyzer.py`: deterministic resume completeness, date, duplicate-skill, and formatting checks.
- `services/job_matcher.py`: deterministic required/preferred skill and experience matching.
- `services/ats_scorer.py`: deterministic normalized scoring built on `JobMatcher` results and evidence checks.
- `tests/test_matcher_evaluation.py`: 30 anonymized matcher cases with expected outcomes/rationales and a reproducible confusion-matrix calculation; also verifies ATS result propagation.
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
- `POST /resume/analyze-job`: accepts multipart `file` (resume PDF) and `job_description` (form field). It calls the existing parse, analyze, job-parse, match, and suggestions route functions directly, without HTTP calls to this app. Returns `ResumeJobAnalysisResponse` with `resume`, `analysis`, `job_requirements`, `job_match`, `suggestions`, and deterministic `ats_score`. Unreadable PDFs return HTTP 400; missing/invalid multipart fields return HTTP 422; Gemini quota/rate limits return HTTP 429 with an available retry delay; other provider/network failures return safe 503 errors; invalid structured provider output returns HTTP 502. The extracted PDF text is reused for the compatibility check; the PDF is not parsed twice.
- `POST /job/parse`: accepts `JobDescriptionRequest { title?: str, description: str }`; parses the description into and returns `JobRequirements`. The current route passes only `description` to the LLM service; `title` is unused.

FastAPI/Pydantic validate JSON request bodies; invalid bodies receive the framework's HTTP 422 response. `JobRequirements` contains required/preferred skills and experience lists. `JobMatch` contains matched/missing required and preferred skills and experience, separate uncertain-tenure lists, matching evidence descriptions, and a summary.

## Service Responsibilities

- `LLMService` creates the Gemini client from `GEMINI_API_KEY` and reads `GEMINI_MODEL`. It implements free-text generation, resume parsing, resume analysis, and job-requirement extraction. Resume parsing retries Gemini server failures up to three attempts with exponential waits; job parsing and analysis do not currently retry.
- `LLMService.suggest_improvements` generates Pydantic-validated suggestions from the supplied resume, analysis, and match; its prompt requires supported evidence and forbids invented candidate claims or metrics. The suggestions route uses `JobMatcher` to remove supported missing skills/experience and retain uncertain tenure before calling the LLM.
- `PDFService` joins extracted text from all PDF pages.
- `DeterministicAnalyzer` checks missing contact details/sections, education date ordering, duplicate skills, and selected PDF extraction artifacts.
- `JobMatcher` normalizes Kafka, Snowflake, AWS S3/Lambda/SQS, DSA, relational-database, REST API, JavaScript, TypeScript, PostgreSQL, concurrency/unit-testing terms, and distributed-caching evidence for a `Distributed Systems` skill requirement. The distributed-caching equivalence is skill-only; experience reliability is not inferred from a caching migration. Experience requirement matching requires at least 75% of normalized concepts to overlap and searches responsibility/project evidence. It finds skill evidence in skills, experience responsibilities, projects, and achievements. Numeric tenure requirements use employment dates with overlapping intervals merged; incomplete dates produce an explicit uncertain result. Matching itself does not call Gemini.
- `ATSScorer` uses `JobMatcher` to score each unique criterion and never calls Gemini. It can be constructed and tested directly from structured `Resume`, `JobRequirements`, and `JobMatch` objects; the score and compatibility checks are fully deterministic.
- `/resume/analyze-job` classifies Gemini `APIError` values using HTTP code and Google status/message. `429` or `RESOURCE_EXHAUSTED` returns 429; retry delay is read from `Retry-After`, Google `RetryInfo.retryDelay`, or an explicit retry duration in the provider message. Provider error bodies are not returned to API clients, and known quota exhaustion is not retried by application code.

## ATS Score Rules

- Category budgets are centralized in `ATSScorer.CATEGORY_WEIGHTS`: job requirements 70 points, relevant experience 20, ATS compatibility 10.
- Required criteria weigh 2; preferred criteria weigh 1. Each category distributes its budget proportionally by criterion weight, so requirement count does not change the category maximum.
- Aliases and compound AWS services are canonicalized and deduplicated. Each AWS service in a grouped criterion is independently evaluated. Experience criteria with a canonical key already scored as a skill do not earn duplicate experience credit.
- Confirmed matches earn their criterion weight; confirmed gaps earn zero. Uncertain criteria earn no points and are excluded from both earned and available category points. The overall score is rounded half-up to an integer after normalizing earned points by the total available points.
- If there are no assessable job criteria, the response uses `status: insufficient_data` and `overall_score: null`. Otherwise status is `calculated`; uncertain criteria/checks remain listed separately and reduce available maximum points rather than being presumed matched or failed.
- ATS compatibility checks are equally weighted within the 10-point category: meaningful extracted text (at least 40 alphanumeric characters and 8 words), at least 2 of 5 structured sections (education, experience, skills, projects, achievements), contact information (email or phone), and employment information (role/company plus dates or responsibilities). Missing extracted text is uncertain. No visual layout or external ATS compatibility is claimed.
- `ats_score` contains `overall_score`, `status`, `category_scores` (`earned_points`, `maximum_points` per category), matched/missing requirements, uncertain items, individual compatibility checks, and a calculation summary.
- These weights, evidence thresholds, and relative criterion weights are initial product choices, not industry standards.

## Tests and Latest Verification

Tests currently cover twenty-two ATS scorer behaviors, three deterministic-analyzer behaviors, twenty-nine matcher behaviors, thirty curated matcher evaluation cases, three `/resume/match-job` endpoint behaviors, twelve `/resume/analyze-job` endpoint behaviors, and five `/resume/suggestions` endpoint behaviors. Endpoint tests monkeypatch LLM service calls, so they do not call Gemini. Latest verified command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -p no:cacheprovider
106 passed, 2 warnings
```

The curated benchmark reports 18 true positives, 12 true negatives, 0 false positives, and 0 false negatives (precision 1.00, recall 1.00); one tenure case is uncertain and is not counted as a match. The benchmark is a small designed regression set, not an estimate of real-world ATS accuracy. The warnings are from Starlette's `httpx` TestClient integration and a deprecated alias used by `google-genai`. The latest run reported 106 test items and did not report a separate test item for root `test_pdf.py`. Pylance reports no errors in the scorer, matcher, or their models; existing duplicate import and exception-chaining suggestions remain in `main.py`.

## Known Limitations and Technical Debt

- In `/resume/analyze`, `DeterministicAnalyzer` can produce `Contact` and `Dates` findings, but `main.py` only appends findings in the `Completeness`, `Experience`, `Skills`, `Projects`, `Formatting`, and `ATS` categories. Contact and date findings are therefore currently dropped from the response.
- Experience matching remains deterministic and heuristic; a 75% normalized-concept overlap threshold reduces single-keyword false positives. Tenure date parsing supports ISO dates, year/month, English month/year, and year-only values; open-ended present/current dates and unrecognized formats are uncertain rather than evaluated against the current date. `Distributed Systems` can be supported by explicit distributed-caching evidence as a skill, but this does not establish distributed-system reliability. Production issue diagnosis still requires evidence of diagnosing a production issue; preventing missed alerts or reviewing incident reports alone is not treated as diagnosis.
- ATS scoring is explainable but heuristic: weights, section/text thresholds, alias equivalence, and experience keyword rules require product calibration. Structured PDF parsing does not establish visual layout or guarantee compatibility with third-party ATS systems.
- The shared PDF parsing helper and `/resume/analyze-job` map Gemini quota/rate-limit errors to HTTP 429; other provider/network failures remain HTTP 503. The orchestration route also maps unreadable PDFs to HTTP 400, request validation failures to HTTP 422, and invalid structured provider output to HTTP 502. Provider failures are logged without returning raw details. No application retries were added; retry timing is advisory and included only when the provider supplies a parseable delay.
- Resume improvement suggestions are prompt-grounded and response-validated, and already-supported missing skills/experience are removed before suggestion generation. The factual correctness of free-text evidence and recommendations still depends on Gemini following the instructions; current tests mock the LLM response and do not evaluate provider-generated output.
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

Current verified capabilities include PDF resume parsing, LLM-backed resume analysis plus deterministic checks, job requirement extraction, alias-aware matching across skill/responsibility/project/achievement evidence, date-aware tenure matching with overlap protection and uncertainty reporting, and a deterministic explainable ATS score on `/resume/analyze-job`.

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