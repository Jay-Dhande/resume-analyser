
from pydantic import BaseModel, Field


class JobMatch(BaseModel):
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)

    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)

    matching_experience: list[str] = Field(default_factory=list)
    matched_experience_requirements: list[str] = Field(default_factory=list)
    missing_experience_requirements: list[str] = Field(default_factory=list)
    uncertain_experience_requirements: list[str] = Field(default_factory=list)

    matched_preferred_experience: list[str] = Field(default_factory=list)
    missing_preferred_experience: list[str] = Field(default_factory=list)
    uncertain_preferred_experience_requirements: list[str] = Field(
        default_factory=list
    )
    summary: str
