import pytest

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


def test_common_skill_aliases_and_rest_api_equivalence():
    resume = Resume(
        skills=[
            "Apache Kafka",
            "SnowFlake",
            "AWS S3",
            "AWS Lambda",
            "AWS SQS",
            "REST API development",
        ]
    )
    job = JobRequirements(
        required_skills=[
            "Kafka",
            "Snowflake",
            "Amazon S3",
            "Lambda",
            "SQS",
            "REST APIs",
        ]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == job.required_skills
    assert result.missing_skills == []


def test_skills_and_experience_match_from_responsibilities_and_projects():
    resume = Resume(
        experience=[
            {
                "company": "Example Co",
                "role": "Engineer",
                "responsibilities": [
                    "Built Apache Kafka consumers and REST APIs"
                ],
            }
        ],
        projects=["Designed a SnowFlake warehouse using AWS S3"],
    )
    job = JobRequirements(
        required_skills=["Kafka", "REST API development", "Snowflake", "S3"],
        required_experience=["Designed a Snowflake data warehouse"],
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == job.required_skills
    assert result.missing_skills == []
    assert result.matched_experience_requirements == job.required_experience
    assert any(item.startswith("Project:") for item in result.matching_experience)


def test_skill_evidence_can_come_from_experience_role():
    resume = Resume(experience=[{"role": "Java Developer"}])
    job = JobRequirements(required_skills=["Java"])

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["Java"]
    assert result.missing_skills == []


def test_aws_service_aliases_do_not_match_a_different_service():
    resume = Resume(skills=["AWS Lambda"])
    job = JobRequirements(required_skills=["AWS S3"])

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == []
    assert result.missing_skills == ["AWS S3"]


def test_latest_output_skills_match_services_dsa_and_relational_database():
    resume = Resume(
        skills=["AWS Lambda", "Amazon S3", "Amazon SQS"],
        achievements=["Solved 800+ Data Structures and Algorithms problems"],
        experience=[
            {
                "responsibilities": [
                    "Improved SQL query optimization and performance"
                ]
            }
        ],
    )
    job = JobRequirements(
        required_skills=[
            "AWS (S3, Lambda, SQS)",
            "DSA",
            "Relational databases",
            "Kubernetes",
        ]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == job.required_skills[:3]
    assert result.missing_skills == ["Kubernetes"]


def test_distributed_caching_supports_distributed_systems_skill_only():
    resume = Resume(
        skills=["Distributed Caching"],
        experience=[
            {
                "responsibilities": [
                    "Migrated distributed caching workflows using Apache Ignite"
                ]
            }
        ],
    )
    job = JobRequirements(required_skills=["Distributed Systems"])

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == ["Distributed Systems"]
    assert result.missing_skills == []


def test_apache_ignite_alone_does_not_support_distributed_systems():
    resume = Resume(
        skills=["Apache Ignite"],
        experience=[
            {
                "responsibilities": [
                    "Used Apache Ignite as a cache implementation"
                ]
            }
        ],
    )
    job = JobRequirements(required_skills=["Distributed Systems"])

    result = JobMatcher().match(resume, job)

    assert result.matched_skills == []
    assert result.missing_skills == ["Distributed Systems"]


@pytest.mark.parametrize(
    ("requirement", "evidence"),
    [
        ("Concurrency", "Concurrent request processing"),
        ("Unit testing", "Unit tests for service behavior"),
    ],
)
def test_explicit_skill_equivalents_match(requirement, evidence):
    result = JobMatcher().match(
        Resume(skills=[evidence]),
        JobRequirements(required_skills=[requirement]),
    )

    assert result.matched_skills == [requirement]
    assert result.missing_skills == []


@pytest.mark.parametrize(
    ("requirement", "responsibility"),
    [
        ("System design", "Designed user interface mockups"),
        ("Unit testing", "Maintained a unit-level metrics dashboard"),
        (
            "Production issue diagnosis",
            "Reviewed production incident reports",
        ),
        (
            "Distributed systems reliability",
            "Migrated distributed caching workflows using Apache Ignite",
        ),
    ],
)
def test_related_but_insufficient_responsibility_does_not_match(
    requirement,
    responsibility,
):
    result = JobMatcher().match(
        Resume(
            experience=[
                {"responsibilities": [responsibility]}
            ]
        ),
        JobRequirements(required_experience=[requirement]),
    )

    assert result.matched_experience_requirements == []
    assert result.missing_experience_requirements == [requirement]


@pytest.mark.parametrize(
    ("requirement", "responsibility"),
    [
        ("System design", "Designed system architecture for backend services"),
        ("Unit testing", "Wrote unit tests for backend services"),
        ("Production issue diagnosis", "Debugged production incidents"),
        (
            "Distributed systems reliability",
            "Improved reliability of distributed systems",
        ),
    ],
)
def test_explicit_responsibility_evidence_matches(requirement, responsibility):
    result = JobMatcher().match(
        Resume(
            experience=[
                {"responsibilities": [responsibility]}
            ]
        ),
        JobRequirements(required_experience=[requirement]),
    )

    assert result.matched_experience_requirements == [requirement]
    assert result.missing_experience_requirements == []


def test_latest_output_experience_requirements_use_resume_evidence():
    resume = Resume(
        experience=[
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "start_date": "2022-01-01",
                "end_date": "2023-03-31",
                "responsibilities": [
                    "Developed and maintained Spring Boot services for backend applications",
                    "Designed REST APIs and integrated internal LLM APIs across applications",
                    "Diagnosed production failures and improved service performance",
                    "Optimized SQL query performance and improved failure handling for distributed applications",
                ],
            }
        ],
        projects=["Implemented cross-application integrations."],
    )
    job = JobRequirements(
        required_experience=[
            "Developing and maintaining backend applications",
            "Designing APIs and integrating services",
            "Diagnosing production issues and improving performance",
            "Database performance and distributed application reliability",
            "1-3 years of experience",
        ]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_experience_requirements == job.required_experience
    assert result.missing_experience_requirements == []
    assert result.uncertain_experience_requirements == []


def test_overlapping_employment_periods_are_counted_once_for_tenure():
    resume = Resume(
        experience=[
            {
                "role": "Intern",
                "start_date": "2024-01-01",
                "end_date": "2024-08-31",
            },
            {
                "role": "Engineer",
                "start_date": "2024-01-01",
                "end_date": "2024-08-31",
            },
        ]
    )
    job = JobRequirements(
        required_experience=["1-3 years of experience"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_experience_requirements == []
    assert result.missing_experience_requirements == [
        "1-3 years of experience"
    ]
    assert result.uncertain_experience_requirements == []


def test_missing_employment_dates_are_reported_as_uncertain_tenure():
    resume = Resume(experience=[{"role": "Software Engineer"}])
    job = JobRequirements(
        required_experience=["1-3 years of experience"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_experience_requirements == []
    assert result.missing_experience_requirements == []
    assert result.uncertain_experience_requirements == [
        "1-3 years of experience"
    ]


def test_present_end_date_does_not_make_supported_responsibility_uncertain():
    resume = Resume(
        experience=[
            {
                "role": "Software Engineer",
                "start_date": "2025-04-01",
                "end_date": "Present",
                "responsibilities": ["Built Spring Boot backend services"],
            }
        ]
    )
    job = JobRequirements(
        required_experience=[
            "Backend development",
            "1-3 years of experience",
        ]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_experience_requirements == ["Backend development"]
    assert result.uncertain_experience_requirements == [
        "1-3 years of experience"
    ]


def test_present_employment_date_is_uncertain_and_time_independent():
    resume = Resume(
        experience=[
            {
                "role": "Engineer",
                "start_date": "2023-01-01",
                "end_date": "Present",
            }
        ]
    )
    job = JobRequirements(
        required_experience=["1-3 years of experience"]
    )

    result = JobMatcher().match(resume, job)

    assert result.matched_experience_requirements == []
    assert result.missing_experience_requirements == []
    assert result.uncertain_experience_requirements == [
        "1-3 years of experience"
    ]


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
    