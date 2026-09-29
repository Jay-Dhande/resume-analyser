from pydantic import BaseModel


class JobMatch(BaseModel):
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    matching_experience: list[str] = []
    missing_requirements: list[str] = []
    summary: str