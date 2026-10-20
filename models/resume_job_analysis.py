from pydantic import BaseModel

from models.analysis import ResumeAnalysis
from models.ats_score import ATSScore
from models.job import JobRequirements
from models.job_match import JobMatch
from models.resume import Resume
from models.suggestions import ResumeSuggestions


class ResumeJobAnalysisResponse(BaseModel):
    resume: Resume
    analysis: ResumeAnalysis
    job_requirements: JobRequirements
    job_match: JobMatch
    suggestions: ResumeSuggestions
    ats_score: ATSScore