from models.resume import Resume
from models.job import JobDescription
from services.job_matcher import JobMatcher


def test_exact_skill_match():
    resume = Resume(
        skills=["Java", "Python", "Kafka"]
    )

    job = JobDescription(
        title="Backend Engineer",
        description="Backend role",
        required_skills=["Java", "Kafka"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["Java", "Kafka"]
    assert result.missing_skills == []


def test_skill_alias_match():
    resume = Resume(
        skills=["AWS Lambda", "Java"]
    )

    job = JobDescription(
        title="Cloud Engineer",
        description="Cloud role",
        required_skills=["AWS", "Java"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["AWS", "Java"]
    assert result.missing_skills == []


def test_missing_skill():
    resume = Resume(
        skills=["Java", "Kafka"]
    )

    job = JobDescription(
        title="Backend Engineer",
        description="Backend role",
        required_skills=["Java", "Kubernetes"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["Java"]
    assert result.missing_skills == ["Kubernetes"]


def test_matching_experience():
    resume = Resume(
        skills=["Java", "Spring Boot"],
        experience=[
            {
                "company": "Goldman Sachs",
                "role": "Software Engineer",
                "responsibilities": [
                    "Built backend services using Java and Spring Boot"
                ]
            }
        ]
    )

    job = JobDescription(
        title="Backend Engineer",
        description="Backend role",
        required_skills=["Java", "Spring Boot"]
    )

    result = JobMatcher().match(resume, job)

    assert len(result.matching_experience) == 1
    assert "Goldman Sachs" in result.matching_experience[0]