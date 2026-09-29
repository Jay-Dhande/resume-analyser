from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile
from io import BytesIO
from fastapi import HTTPException
from google.genai import errors
from models.resume import Resume
from services.llm_service import LLMService
from services.pdf_service import PDFService
from services.deterministic_analyzer import DeterministicAnalyzer
from models.job import JobDescription
from services.job_matcher import JobMatcher

load_dotenv()

app = FastAPI()

llm_service = LLMService()
pdf_service = PDFService()
deterministic_analyzer = DeterministicAnalyzer()
job_matcher = JobMatcher()


class ChatRequest(BaseModel):
    prompt: str


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

@app.post("/resume/match")
def match_resume(
    resume: Resume,
    job: JobDescription
):
    return job_matcher.match(resume, job)