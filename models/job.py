from pydantic import BaseModel


class JobDescription(BaseModel):
    title: str | None = None
    description: str
    required_skills: list[str] = []