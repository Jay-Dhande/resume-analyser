import pytest

from models.job import JobRequirements
from models.resume import Resume
from services.ats_scorer import ATSScorer
from services.job_matcher import JobMatcher


EXTRACTED_TEXT = (
    "Jay Doe Software Engineer resume email jay@example.com phone "
    "5551234567 professional experience education skills and projects"
)


def make_resume(**overrides):
    values = {
        "name": "Jay Doe",
        "email": "jay@example.com",
        "phone": "5551234567",
        "education": [{"institution": "Example University"}],
        "skills": ["Java", "Apache Kafka"],
        "experience": [
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "start_date": "2022-01-01",
                "end_date": "2023-06-30",
                "responsibilities": [
                    "Built Spring Boot backend services",
                    "Developed REST APIs and integrated services",
                ],
            }
        ],
        "projects": ["Built a Kafka consumer project"],
        "achievements": [],
    }
    values.update(overrides)
    return Resume(**values)


def score(resume, requirements, extracted_text=EXTRACTED_TEXT):
    matcher = JobMatcher()
    job_match = matcher.match(resume, requirements)
    return ATSScorer(matcher).score(
        resume,
        requirements,
        job_match,
        extracted_text,
    )


def test_strong_match_earns_all_category_points():
    resume = make_resume()
    requirements = JobRequirements(
        required_skills=["Java"],
        preferred_skills=["Kafka"],
        required_experience=["Developed backend applications"],
    )

    result = score(resume, requirements)

    assert result.status == "calculated"
    assert result.overall_score == 100
    assert result.category_scores["job_requirements"].earned_points == 70
    assert result.category_scores["relevant_experience"].earned_points == 20
    assert result.category_scores["ats_compatibility"].earned_points == 10
    assert result.missing_requirements == []
    assert result.uncertain_items == []


def test_weak_partial_and_strong_scores_are_ordered():
    strong = score(
        make_resume(),
        JobRequirements(
            required_skills=["Java"],
            required_experience=["Developed backend applications"],
        ),
    )
    partial = score(
        make_resume(skills=["SQL"]),
        JobRequirements(
            required_skills=["Python"],
            preferred_skills=["SQL"],
        ),
    )
    weak = score(
        Resume(skills=["Java"]),
        JobRequirements(required_skills=["Python", "Kafka"]),
        extracted_text="",
    )

    assert weak.overall_score < partial.overall_score < strong.overall_score


def test_required_criteria_weigh_twice_as_much_as_preferred():
    resume = make_resume(skills=["SQL"])
    requirements = JobRequirements(
        required_skills=["Python"],
        preferred_skills=["SQL"],
    )

    result = score(resume, requirements)

    requirement_score = result.category_scores["job_requirements"]
    assert requirement_score.earned_points == 23.33
    assert requirement_score.maximum_points == 70
    assert result.missing_requirements == ["Required skill: Python"]


def test_compound_aws_services_are_scored_individually():
    resume = make_resume(skills=["AWS S3", "AWS Lambda"])
    requirements = JobRequirements(
        required_skills=["AWS (S3, Lambda, SQS)"]
    )

    result = score(resume, requirements)

    assert result.matched_requirements == [
        "Required skill: AWS S3",
        "Required skill: AWS Lambda",
    ]
    assert result.missing_requirements == ["Required skill: AWS SQS"]
    assert result.category_scores["job_requirements"].earned_points == 46.67


def test_achievements_can_support_dsa_and_sql_supports_relational_database():
    resume = make_resume(
        skills=[],
        achievements=["Solved 800+ Data Structures and Algorithms problems"],
        experience=[
            {
                "company": "Example Co",
                "role": "Engineer",
                "responsibilities": ["Improved SQL query performance"],
            }
        ],
    )
    requirements = JobRequirements(
        required_skills=["DSA", "Relational databases"]
    )

    result = score(resume, requirements)

    assert result.matched_requirements == [
        "Required skill: DSA",
        "Required skill: Relational databases",
    ]
    assert result.missing_requirements == []


def test_manual_case_scores_only_supported_responsibility_evidence():
    resume = make_resume(
        skills=["Distributed Caching", "SQL"],
        experience=[
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "start_date": "2025-04-01",
                "end_date": "Present",
                "responsibilities": [
                    "Migrated distributed caching workflows using Apache Ignite",
                    "Built Spring Boot backend services",
                    "Optimized SQL queries and caching workflows",
                    "Enhanced a financial alerting system to prevent missed alerts",
                ],
            }
        ],
    )
    requirements = JobRequirements(
        required_skills=["Distributed Systems"],
        required_experience=[
            "Backend development",
            "Database optimization",
            "Production issue diagnosis",
            "Distributed systems reliability",
        ],
    )

    result = score(resume, requirements)

    assert result.matched_requirements == [
        "Required skill: Distributed Systems",
        "Required experience: Backend development",
        "Required experience: Database optimization",
    ]
    assert result.missing_requirements == [
        "Required experience: Production issue diagnosis",
        "Required experience: Distributed systems reliability",
    ]
    assert result.uncertain_items == []
    assert result.category_scores["relevant_experience"].earned_points == 10
    assert result.category_scores["relevant_experience"].maximum_points == 20


def test_apache_ignite_alone_does_not_earn_distributed_systems_points():
    resume = make_resume(
        skills=["Apache Ignite"],
        experience=[
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "responsibilities": [
                    "Used Apache Ignite as a cache implementation"
                ],
            }
        ],
    )
    requirements = JobRequirements(required_skills=["Distributed Systems"])

    result = score(resume, requirements)

    assert result.matched_requirements == []
    assert result.missing_requirements == [
        "Required skill: Distributed Systems"
    ]
    assert result.category_scores["job_requirements"].earned_points == 0


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
def test_related_but_insufficient_evidence_does_not_earn_experience_points(
    requirement,
    responsibility,
):
    resume = make_resume(
        experience=[
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "responsibilities": [responsibility],
            }
        ],
        projects=[],
    )

    result = score(
        resume,
        JobRequirements(required_experience=[requirement]),
    )

    assert result.matched_requirements == []
    assert result.missing_requirements == [
        f"Required experience: {requirement}"
    ]
    assert result.category_scores["relevant_experience"].earned_points == 0


def test_explicit_backend_quality_responsibilities_earn_experience_points():
    resume = make_resume(
        experience=[
            {
                "company": "Example Co",
                "role": "Software Engineer",
                "responsibilities": [
                    "Designed system architecture for backend services",
                    "Wrote unit tests for service behavior",
                    "Debugged production incidents",
                    "Improved reliability of distributed systems",
                ],
            }
        ],
        projects=[],
    )
    requirements = JobRequirements(
        required_experience=[
            "System design",
            "Unit testing",
            "Production issue diagnosis",
            "Distributed systems reliability",
        ]
    )

    result = score(resume, requirements)

    assert result.matched_requirements == [
        f"Required experience: {requirement}"
        for requirement in requirements.required_experience
    ]
    assert result.missing_requirements == []
    assert result.category_scores["relevant_experience"].earned_points == 20


def test_aliases_and_repeated_mentions_do_not_duplicate_credit():
    resume = make_resume(
        skills=["JavaScript", "JavaScript"],
        projects=["Used JS; JavaScript project; JavaScript project"],
    )
    requirements = JobRequirements(
        required_skills=["JavaScript", "JS"],
        preferred_skills=["JavaScript"],
    )

    result = score(resume, requirements)

    assert result.matched_requirements == ["Required skill: JavaScript"]
    assert result.category_scores["job_requirements"].earned_points == 70
    assert result.category_scores["job_requirements"].maximum_points == 70


def test_responsibility_scope_is_scored_separately_without_skill_double_count():
    resume = make_resume(skills=["Java"])
    requirements = JobRequirements(
        required_skills=["Java"],
        required_experience=["Experience with Java"],
        preferred_experience=["Developed backend applications"],
    )

    result = score(resume, requirements)

    experience_score = result.category_scores["relevant_experience"]
    assert experience_score.earned_points == 20
    assert experience_score.maximum_points == 20
    assert result.matched_requirements == [
        "Required skill: Java",
        "Preferred experience: Developed backend applications",
    ]


def test_tenure_uncertainty_is_excluded_from_points_and_reported():
    resume = make_resume(
        skills=["Java"],
        experience=[
            {
                "company": "Example Co",
                "role": "Engineer",
                "responsibilities": ["Built Java services"],
            }
        ],
    )
    requirements = JobRequirements(
        required_skills=["Java"],
        required_experience=["1-3 years of experience"],
    )

    result = score(resume, requirements)

    assert result.status == "calculated"
    assert result.category_scores["relevant_experience"].maximum_points == 0
    assert result.uncertain_items == [
        "Required experience: 1-3 years of experience (evidence is insufficient to assess)"
    ]


def test_overlapping_employment_dates_do_not_earn_tenure_credit():
    resume = make_resume(
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
    requirements = JobRequirements(
        required_experience=["1+ years of experience"]
    )

    result = score(resume, requirements)

    assert result.missing_requirements == [
        "Required experience: 1+ years of experience"
    ]
    assert result.uncertain_items == []
    assert result.category_scores["relevant_experience"].earned_points == 0


def test_unknown_extraction_text_is_an_uncertain_compatibility_check():
    resume = make_resume()
    requirements = JobRequirements(required_skills=["Java"])

    result = score(resume, requirements, extracted_text=None)

    check = next(
        check for check in result.compatibility_checks
        if check.name == "meaningful_extracted_text"
    )
    assert check.status == "uncertain"
    assert result.category_scores["ats_compatibility"].maximum_points == 7.5
    assert any("meaningful_extracted_text" in item for item in result.uncertain_items)


def test_weak_match_and_ats_failures_score_zero():
    resume = Resume(skills=["Java"])
    requirements = JobRequirements(required_skills=["Python", "Kafka"])

    result = score(resume, requirements, extracted_text="")

    assert result.status == "calculated"
    assert result.overall_score == 0
    assert len(result.missing_requirements) == 2
    assert all(check.status == "fail" for check in result.compatibility_checks)


def test_no_job_criteria_returns_insufficient_data():
    result = score(make_resume(), JobRequirements())

    assert result.status == "insufficient_data"
    assert result.overall_score is None
    assert "No assessable job criterion" in result.calculation_summary


def test_empty_resume_and_unassessable_requirements_are_insufficient():
    result = score(
        Resume(),
        JobRequirements(
            required_skills=["Python"],
            required_experience=["Develop backend applications"],
        ),
        extracted_text=None,
    )

    assert result.status == "insufficient_data"
    assert result.overall_score is None
    assert result.matched_requirements == []
    assert result.missing_requirements == []
    assert len(result.uncertain_items) == 3
    assert result.category_scores["job_requirements"].maximum_points == 0
    assert result.category_scores["relevant_experience"].maximum_points == 0


def test_blank_requirement_is_not_scored_as_a_match():
    result = score(
        make_resume(),
        JobRequirements(required_skills=["   "]),
    )

    assert result.status == "insufficient_data"
    assert result.overall_score is None
    assert result.matched_requirements == []
    assert result.missing_requirements == []


def test_score_and_breakdown_are_stable_for_identical_inputs():
    resume = make_resume()
    requirements = JobRequirements(
        required_skills=["Java", "Kafka"],
        required_experience=["Developed backend applications"],
    )

    first = score(resume, requirements).model_dump()
    second = score(resume, requirements).model_dump()

    assert first == second