from pydantic import BaseModel


class Finding(BaseModel):
    category: str
    issue: str
    evidence: str
    suggestion: str
    severity: str
    source: str


class ResumeAnalysis(BaseModel):
    summary: str

    completeness: list[Finding] = []
    experience: list[Finding] = []
    skills: list[Finding] = []
    projects: list[Finding] = []
    ats: list[Finding] = []

    strengths: list[str] = []