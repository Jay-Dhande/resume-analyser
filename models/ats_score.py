from typing import Literal

from pydantic import BaseModel, Field


class ATSCategoryScore(BaseModel):
    earned_points: float = Field(ge=0)
    maximum_points: float = Field(ge=0)


class ATSCompatibilityCheck(BaseModel):
    name: str
    status: Literal["pass", "fail", "uncertain"]
    explanation: str


class ATSScore(BaseModel):
    overall_score: int | None = Field(default=None, ge=0, le=100)
    status: Literal["calculated", "insufficient_data"]
    category_scores: dict[str, ATSCategoryScore]
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    uncertain_items: list[str] = Field(default_factory=list)
    compatibility_checks: list[ATSCompatibilityCheck] = Field(
        default_factory=list
    )
    calculation_summary: str