import logging
import math
import re

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import FastAPI, File, Form, UploadFile
import httpx
from io import BytesIO
from fastapi import HTTPException
from google.genai import errors
from pydantic import ValidationError
from pypdf.errors import PdfReadError
from models.resume import Resume
from models.analysis import ResumeAnalysis
from services.ats_scorer import ATSScorer
from models.job_match import JobMatch
from models.suggestions import ResumeSuggestions
from models.resume_job_analysis import ResumeJobAnalysisResponse
from services.llm_service import LLMService
from services.pdf_service import PDFService
from services.deterministic_analyzer import DeterministicAnalyzer
from models.job import JobDescription
from services.job_matcher import JobMatcher
from models.job import JobRequirements

load_dotenv()

app = FastAPI()
logger = logging.getLogger(__name__)

llm_service = LLMService()
pdf_service = PDFService()
deterministic_analyzer = DeterministicAnalyzer()
job_matcher = JobMatcher()
ats_scorer = ATSScorer(job_matcher)


def _retry_delay_seconds(value) -> int | None:
    if isinstance(value, (int, float)):
        return math.ceil(value) if value > 0 else None
    if not isinstance(value, str):
        return None

    numeric_value = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", value)
    if numeric_value:
        seconds = float(numeric_value.group(1))
        return math.ceil(seconds) if seconds > 0 else None

    duration = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*s\s*", value)
    if duration:
        seconds = float(duration.group(1))
        return math.ceil(seconds) if seconds > 0 else None

    retry_message = re.search(
        r"\bretry\s+(?:in|after)\s+(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b",
        value,
        re.IGNORECASE,
    )
    if not retry_message:
        return None

    amount = float(retry_message.group(1))
    unit = retry_message.group(2).lower()
    multiplier = (
        86400 if unit.startswith("d")
        else 3600 if unit.startswith("h")
        else 60 if unit.startswith("m")
        else 1
    )
    seconds = amount * multiplier
    return math.ceil(seconds) if seconds > 0 else None


def _find_retry_delay(payload) -> int | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() == "retrydelay":
                delay = _retry_delay_seconds(value)
                if delay is not None:
                    return delay
            delay = _find_retry_delay(value)
            if delay is not None:
                return delay
    elif isinstance(payload, list):
        for value in payload:
            delay = _find_retry_delay(value)
            if delay is not None:
                return delay
    return None


def _gemini_retry_delay_seconds(provider_error: errors.APIError) -> int | None:
    headers = getattr(getattr(provider_error, "response", None), "headers", {})
    delay = _retry_delay_seconds(headers.get("Retry-After"))
    if delay is not None:
        return delay

    delay = _find_retry_delay(getattr(provider_error, "details", None))
    if delay is not None:
        return delay
    return _retry_delay_seconds(getattr(provider_error, "message", None))


def _is_gemini_quota_error(provider_error: errors.APIError) -> bool:
    code = getattr(provider_error, "code", None)
    status = str(getattr(provider_error, "status", "")).upper()
    message = str(getattr(provider_error, "message", "")).upper()
    return code == 429 or status == "RESOURCE_EXHAUSTED" or (
        "RESOURCE_EXHAUSTED" in message
    )


def _gemini_api_http_exception(
    provider_error: errors.APIError,
    operation: str,
) -> HTTPException:
    if _is_gemini_quota_error(provider_error):
        retry_delay = _gemini_retry_delay_seconds(provider_error)
        logger.warning(
            "Gemini quota/rate limit reached during %s (code=%s, status=%s, retry_after_seconds=%s)",
            operation,
            getattr(provider_error, "code", None),
            getattr(provider_error, "status", None),
            retry_delay,
        )
        detail = "Gemini quota or rate limit reached. Check your quota and billing."
        headers = None
        if retry_delay is not None:
            detail += f" Retry after approximately {retry_delay} seconds."
            headers = {"Retry-After": str(retry_delay)}
        else:
            detail += " Retry after quota becomes available."
        return HTTPException(status_code=429, detail=detail, headers=headers)

    logger.exception(
        "Gemini API request failed during %s (code=%s, status=%s)",
        operation,
        getattr(provider_error, "code", None),
        getattr(provider_error, "status", None),
    )
    return HTTPException(
        status_code=503,
        detail="Resume analysis service is temporarily unavailable. Please try again later.",
    )


class ChatRequest(BaseModel):
    prompt: str
    
class JobDescriptionRequest(BaseModel):
    title: str | None = None
    description: str    


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    response = llm_service.generate(request.prompt)

    return {"response": response}

async def parse_resume_upload(file: UploadFile) -> tuple[Resume, str]:
    contents = await file.read()
    extracted_text = pdf_service.extract_text(BytesIO(contents))
    try:
        resume = llm_service.parse_resume(extracted_text)
    except errors.APIError as exc:
        raise _gemini_api_http_exception(exc, "resume parsing") from exc
    return resume, extracted_text

@app.post("/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    resume, _ = await parse_resume_upload(file)
    return resume

@app.post("/resume/analyze")
def analyze_resume(resume: Resume):
    llm_analysis = llm_service.analyze_resume(resume)

    deterministic_findings = deterministic_analyzer.analyze(resume)

    for finding in deterministic_findings:
        if finding.category == "Completeness":
            llm_analysis.completeness.append(finding)

        elif finding.category == "Experience":
            llm_analysis.experience.append(finding)

        elif finding.category == "Skills":
            llm_analysis.skills.append(finding)

        elif finding.category == "Projects":
            llm_analysis.projects.append(finding)

        elif finding.category == "Formatting":
            llm_analysis.ats.append(finding)

        elif finding.category == "ATS":
            llm_analysis.ats.append(finding)

    return llm_analysis

class ResumeMatchRequest(BaseModel):
    resume: Resume
    job: JobRequirements    

class ResumeJobMatchRequest(BaseModel):
    resume: Resume
    job_description: str

class ResumeSuggestionsRequest(BaseModel):
    resume: Resume
    analysis: ResumeAnalysis
    job_match: JobMatch

@app.post("/resume/match")
def match_resume(request: ResumeMatchRequest):
    return job_matcher.match(
        request.resume,
        request.job
    )

@app.post("/resume/match-job")
def match_resume_to_job(request: ResumeJobMatchRequest):
    try:
        job_requirements = llm_service.parse_job_description(
            request.job_description
        )
    except errors.ServerError:
        raise HTTPException(
            status_code=503,
            detail="Job parsing service is temporarily unavailable. Please try again later."
        )

    return job_matcher.match(request.resume, job_requirements)

@app.post("/resume/suggestions", response_model=ResumeSuggestions)
def suggest_resume_improvements(request: ResumeSuggestionsRequest):
    job_match = job_matcher.filter_supported_missing_requirements(
        request.resume,
        request.job_match,
    )
    try:
        suggestions = llm_service.suggest_improvements(
            request.resume,
            request.analysis,
            job_match,
        )
    except errors.ServerError:
        raise HTTPException(
            status_code=503,
            detail="Resume suggestions service is temporarily unavailable. Please try again later."
        )

    category_order = {
        "missing_required_skill": 0,
        "missing_required_experience": 1,
        "resume_quality": 2,
    }
    suggestions.suggestions.sort(
        key=lambda suggestion: category_order[suggestion.category]
    )
    return suggestions

@app.post("/resume/analyze-job", response_model=ResumeJobAnalysisResponse)
async def analyze_resume_job(
    file: UploadFile = File(...),
    job_description: str = Form(...),
):
    try:
        resume, extracted_text = await parse_resume_upload(file)
    except PdfReadError as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid or readable PDF.",
        ) from exc
    except ValidationError as exc:
        logger.warning(
            "Invalid structured resume response in /resume/analyze-job (%d validation errors)",
            len(exc.errors()),
        )
        raise HTTPException(
            status_code=502,
            detail="The resume parsing service returned an invalid response.",
        ) from exc
    except HTTPException as exc:
        if exc.status_code >= 500:
            logger.exception("Resume parsing step failed in /resume/analyze-job")
        raise
    except httpx.RequestError as exc:
        logger.exception("Network request failed during resume parsing")
        raise HTTPException(
            status_code=503,
            detail="Resume analysis service is temporarily unavailable. Please try again later.",
        ) from exc
    except errors.APIError as exc:
        raise _gemini_api_http_exception(exc, "resume parsing") from exc
    except Exception as exc:
        logger.exception("Unexpected failure during resume parsing")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while analyzing the resume.",
        ) from exc

    try:
        analysis = analyze_resume(resume)
        job_requirements = parse_job(
            JobDescriptionRequest(description=job_description)
        )
        job_match = match_resume(
            ResumeMatchRequest(resume=resume, job=job_requirements)
        )
        suggestions = suggest_resume_improvements(
            ResumeSuggestionsRequest(
                resume=resume,
                analysis=analysis,
                job_match=job_match,
            )
        )
        ats_score = ats_scorer.score(
            resume,
            job_requirements,
            job_match,
            extracted_text,
        )
    except HTTPException as exc:
        if exc.status_code >= 500:
            logger.exception("Provider-backed step failed in /resume/analyze-job")
        raise
    except httpx.RequestError as exc:
        logger.exception("Network request failed in /resume/analyze-job")
        raise HTTPException(
            status_code=503,
            detail="Resume analysis service is temporarily unavailable. Please try again later.",
        ) from exc
    except errors.APIError as exc:
        raise _gemini_api_http_exception(
            exc,
            "/resume/analyze-job",
        ) from exc
    except ValidationError as exc:
        logger.warning(
            "Invalid structured provider response in /resume/analyze-job (%d validation errors)",
            len(exc.errors()),
        )
        raise HTTPException(
            status_code=502,
            detail="The resume analysis service returned an invalid response.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected failure in /resume/analyze-job")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while analyzing the resume.",
        ) from exc

    return ResumeJobAnalysisResponse(
        resume=resume,
        analysis=analysis,
        job_requirements=job_requirements,
        job_match=job_match,
        suggestions=suggestions,
        ats_score=ats_score,
    )

@app.post("/job/parse")
def parse_job(request: JobDescriptionRequest):
    return llm_service.parse_job_description(
        request.description
    )
    
