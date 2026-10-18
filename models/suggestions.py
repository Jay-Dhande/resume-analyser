from typing import Literal

from pydantic import BaseModel, Field


class ImprovementSuggestion(BaseModel):
    category: Literal[
        "missing_required_skill",
        "missing_required_experience",
        "resume_quality",
    ]
    priority: Literal["high", "medium", "low"]
    issue: str
    evidence: str
    recommendation: str


class ResumeSuggestions(BaseModel):
    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)