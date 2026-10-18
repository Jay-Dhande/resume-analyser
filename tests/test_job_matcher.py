from models.resume import Resume
from models.job import JobRequirements
from services.job_matcher import JobMatcher
from models.resume import Resume
from models.job import JobRequirements
from services.job_matcher import JobMatcher


def test_exact_skill_match():
    resume = Resume(
        skills=["Java", "Python", "Kafka"]
    )

    job = JobRequirements(
        required_skills=["Java", "Kafka"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["Java", "Kafka"]
    assert result.missing_skills == []


def test_skill_alias_match():
    resume = Resume(
        skills=["AWS Lambda", "Java"]
    )

    job = JobRequirements(
        required_skills=["AWS", "Java"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["AWS", "Java"]
    assert result.missing_skills == []


def test_missing_skill():
    resume = Resume(
        skills=["Java", "Kafka"]
    )

    job = JobRequirements(
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

    job = JobRequirements(
        required_skills=["Java", "Spring Boot"]
    )

    result = JobMatcher().match(resume, job)

    assert len(result.matching_experience) == 1
    assert "Goldman Sachs" in result.matching_experience[0]
    

def test_required_experience_matched():
    resume = Resume(
        experience=[
            {
                "company": "Goldman Sachs",
                "role": "Software Engineer",
                "responsibilities": [
                    "Built backend services using Java and Spring Boot"
                ],
            }
        ]
    )

    job = JobRequirements(
        required_experience=["Built backend services using Java"]
    )

    result = JobMatcher().match(resume, job)

    assert "Built backend services using Java" in (
        result.matched_experience_requirements
    )
    assert result.missing_experience_requirements == []


def test_required_experience_missing():
    resume = Resume(
        experience=[
            {
                "company": "Goldman Sachs",
                "role": "Software Engineer",
                "responsibilities": [
                    "Built backend services using Java"
                ],
            }
        ]
    )

    job = JobRequirements(
        required_experience=["Experience with Kubernetes deployment"]
    )

    result = JobMatcher().match(resume, job)

    assert result.missing_experience_requirements == [
        "Experience with Kubernetes deployment"
    ]


def test_preferred_experience_matched():
    resume = Resume(
        experience=[
            {
                "company": "Goldman Sachs",
                "role": "Software Engineer",
                "responsibilities": [
                    "Developed REST APIs using Spring Boot"
                ],
            }
        ]
    )

    job = JobRequirements(
        preferred_experience=["Developed REST APIs"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_preferred_experience == [
        "Developed REST APIs"
    ]
    assert result.missing_preferred_experience == []
    