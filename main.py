from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile
from io import BytesIO
from fastapi import HTTPException
from google.genai import errors
from models.resume import Resume
from models.analysis import ResumeAnalysis
from models.job_match import JobMatch
from models.suggestions import ResumeSuggestions
from services.llm_service import LLMService
from services.pdf_service import PDFService
from services.deterministic_analyzer import DeterministicAnalyzer
from models.job import JobDescription
from services.job_matcher import JobMatcher
from models.job import JobRequirements

load_dotenv()

app = FastAPI()

llm_service = LLMService()
pdf_service = PDFService()
deterministic_analyzer = DeterministicAnalyzer()
job_matcher = JobMatcher()


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

@app.post("/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    contents = await file.read()

    resume_text = pdf_service.extract_text(BytesIO(contents))

    try:
        resume = llm_service.parse_resume(resume_text)
    except errors.ServerError:
        raise HTTPException(
            status_code=503,
            detail="Resume parsing service is temporarily unavailable. Please try again later."
        )

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
            llm_analysis.formatting.append(finding)

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
    try:
        suggestions = llm_service.suggest_improvements(
            request.resume,
            request.analysis,
            request.job_match,
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

@app.post("/job/parse")
def parse_job(request: JobDescriptionRequest):
    return llm_service.parse_job_description(
        request.description
    )
    
