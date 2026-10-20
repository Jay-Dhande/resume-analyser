import pytest

from models.job import JobRequirements
from models.resume import Resume
from services.ats_scorer import ATSScorer
from services.job_matcher import JobMatcher


EXTRACTED_TEXT = (
    "Backend engineering resume with contact details, skills, education, "
    "professional experience, projects, and technical achievements."
)

MATCHER_CASES = [
    {
        "name": "java skill",
        "kind": "skill",
        "evidence": [("skills", "Java")],
        "requirement": "Java",
        "expected": "match",
        "rationale": "Exact listed skill evidence.",
    },
    {
        "name": "kafka alias in project",
        "kind": "skill",
        "evidence": [("projects", "Built an Apache Kafka consumer")],
        "requirement": "Kafka",
        "expected": "match",
        "rationale": "Apache Kafka is an explicit alias for Kafka.",
    },
    {
        "name": "snowflake case normalization",
        "kind": "skill",
        "evidence": [("skills", "SnowFlake")],
        "requirement": "Snowflake",
        "expected": "match",
        "rationale": "Case differences do not alter the named skill.",
    },
    {
        "name": "aws s3 service alias",
        "kind": "skill",
        "evidence": [("skills", "Amazon S3")],
        "requirement": "AWS S3",
        "expected": "match",
        "rationale": "Amazon S3 and AWS S3 denote the same service.",
    },
    {
        "name": "aws sqs service alias",
        "kind": "skill",
        "evidence": [("skills", "AWS SQS")],
        "requirement": "Amazon SQS",
        "expected": "match",
        "rationale": "The listed AWS service is the required SQS service.",
    },
    {
        "name": "all compound aws services present",
        "kind": "skill",
        "evidence": [("skills", "AWS S3, AWS Lambda, AWS SQS")],
        "requirement": "AWS (S3, Lambda, SQS)",
        "expected": "match",
        "rationale": "Each required compound component has evidence.",
    },
    {
        "name": "partial compound aws services",
        "kind": "skill",
        "evidence": [("skills", "AWS S3 and AWS Lambda")],
        "requirement": "AWS (S3, Lambda, SQS)",
        "expected": "no match",
        "rationale": "The grouped matcher requires every listed service; scorer component credit is tested separately.",
    },
    {
        "name": "aws services are not interchangeable",
        "kind": "skill",
        "evidence": [("skills", "AWS Lambda")],
        "requirement": "AWS S3",
        "expected": "no match",
        "rationale": "Lambda is not evidence of S3.",
    },
    {
        "name": "dsa evidence in achievement",
        "kind": "skill",
        "evidence": [("achievements", "Solved data structures and algorithms problems")],
        "requirement": "DSA",
        "expected": "match",
        "rationale": "The achievement explicitly spells out DSA.",
    },
    {
        "name": "relational database from sql responsibility",
        "kind": "skill",
        "evidence": [("responsibilities", "Optimized SQL queries for a reporting database")],
        "requirement": "Relational databases",
        "expected": "match",
        "rationale": "SQL query work is explicit relational-database evidence.",
    },
    {
        "name": "generic database label is insufficient",
        "kind": "skill",
        "evidence": [("skills", "Database")],
        "requirement": "Relational databases",
        "expected": "no match",
        "rationale": "The resume names no relational database technology or SQL work.",
    },
    {
        "name": "distributed caching listed as skill",
        "kind": "skill",
        "evidence": [("skills", "Distributed Caching")],
        "requirement": "Distributed Systems",
        "expected": "match",
        "rationale": "This is the explicit skill-only distributed-caching equivalence.",
    },
    {
        "name": "distributed caching workflow responsibility",
        "kind": "skill",
        "evidence": [("responsibilities", "Migrated distributed caching workflows")],
        "requirement": "Distributed Systems",
        "expected": "match",
        "rationale": "The responsibility explicitly describes distributed caching.",
    },
    {
        "name": "apache ignite name alone",
        "kind": "skill",
        "evidence": [("skills", "Apache Ignite")],
        "requirement": "Distributed Systems",
        "expected": "no match",
        "rationale": "A technology name alone does not state distributed-systems evidence.",
    },
    {
        "name": "redis name alone",
        "kind": "skill",
        "evidence": [("skills", "Redis")],
        "requirement": "Distributed Systems",
        "expected": "no match",
        "rationale": "Redis alone does not establish distributed-systems work.",
    },
    {
        "name": "generic cache mention",
        "kind": "skill",
        "evidence": [("projects", "Added an in-memory cache for lookup results")],
        "requirement": "Distributed Systems",
        "expected": "no match",
        "rationale": "Generic caching is not explicitly distributed caching.",
    },
    {
        "name": "concurrent request processing",
        "kind": "experience",
        "evidence": [("responsibilities", "Handled concurrent request processing")],
        "requirement": "Concurrency",
        "expected": "match",
        "rationale": "Concurrent processing is an explicit equivalent for concurrency.",
    },
    {
        "name": "backend development",
        "kind": "experience",
        "evidence": [("responsibilities", "Built Spring Boot backend services")],
        "requirement": "Backend development",
        "expected": "match",
        "rationale": "The responsibility explicitly describes backend service development.",
    },
    {
        "name": "database optimization",
        "kind": "experience",
        "evidence": [("responsibilities", "Optimized SQL query performance")],
        "requirement": "Database optimization",
        "expected": "match",
        "rationale": "SQL and optimization are both directly evidenced.",
    },
    {
        "name": "system architecture design",
        "kind": "experience",
        "evidence": [("responsibilities", "Designed system architecture for backend services")],
        "requirement": "System design",
        "expected": "match",
        "rationale": "System architecture design directly demonstrates system design.",
    },
    {
        "name": "ui mockup design",
        "kind": "experience",
        "evidence": [("responsibilities", "Designed user interface mockups")],
        "requirement": "System design",
        "expected": "no match",
        "rationale": "UI mockup design does not demonstrate system architecture design.",
    },
    {
        "name": "unit tests",
        "kind": "experience",
        "evidence": [("responsibilities", "Wrote unit tests for service behavior")],
        "requirement": "Unit testing",
        "expected": "match",
        "rationale": "Writing unit tests directly demonstrates unit testing.",
    },
    {
        "name": "unit level dashboard",
        "kind": "experience",
        "evidence": [("responsibilities", "Maintained a unit-level metrics dashboard")],
        "requirement": "Unit testing",
        "expected": "no match",
        "rationale": "A unit-level dashboard does not state testing activity.",
    },
    {
        "name": "production debugging",
        "kind": "experience",
        "evidence": [("responsibilities", "Debugged production incidents")],
        "requirement": "Production issue diagnosis",
        "expected": "match",
        "rationale": "Debugging production incidents directly supports diagnosis.",
    },
    {
        "name": "incident report review",
        "kind": "experience",
        "evidence": [("responsibilities", "Reviewed production incident reports")],
        "requirement": "Production issue diagnosis",
        "expected": "no match",
        "rationale": "Reviewing reports does not establish diagnosing or debugging incidents.",
    },
    {
        "name": "distributed reliability work",
        "kind": "experience",
        "evidence": [("responsibilities", "Improved reliability of distributed systems")],
        "requirement": "Distributed systems reliability",
        "expected": "match",
        "rationale": "The responsibility directly states reliability work on distributed systems.",
    },
    {
        "name": "distributed caching migration is not reliability",
        "kind": "experience",
        "evidence": [("responsibilities", "Migrated distributed caching workflows using Apache Ignite")],
        "requirement": "Distributed systems reliability",
        "expected": "no match",
        "rationale": "A migration alone does not establish reliability improvements.",
    },
    {
        "name": "three of four concepts reaches threshold",
        "kind": "experience",
        "evidence": [("responsibilities", "Designed APIs for backend services")],
        "requirement": "Designing APIs and integrating services",
        "expected": "match",
        "rationale": "Three of four normalized concepts meet the documented 75% threshold.",
    },
    {
        "name": "two of four concepts falls below threshold",
        "kind": "experience",
        "evidence": [("responsibilities", "Designed APIs")],
        "requirement": "Designing APIs and integrating services",
        "expected": "no match",
        "rationale": "Two of four normalized concepts do not reach the 75% threshold.",
    },
    {
        "name": "present date leaves tenure uncertain",
        "kind": "experience",
        "evidence": [("responsibilities", "Built backend services")],
        "requirement": "1-3 years of experience",
        "expected": "no match",
        "expected_uncertain": True,
        "experience_dates": ("2024-01-01", "Present"),
        "rationale": "An open-ended date cannot confirm or deny tenure deterministically.",
    },
]


def resume_for_case(case):
    resume_values = {
        "skills": [],
        "projects": [],
        "achievements": [],
        "experience": [],
    }
    for source, text in case["evidence"]:
        if source == "responsibilities":
            if not resume_values["experience"]:
                resume_values["experience"].append({"responsibilities": []})
            resume_values["experience"][0]["responsibilities"].append(text)
        else:
            resume_values[source].append(text)

    if "experience_dates" in case:
        start_date, end_date = case["experience_dates"]
        if not resume_values["experience"]:
            resume_values["experience"].append({"responsibilities": []})
        resume_values["experience"][0].update(
            {"start_date": start_date, "end_date": end_date}
        )
    return Resume(**resume_values)


def matcher_case_status(case):
    resume = resume_for_case(case)
    job = JobRequirements(
        required_skills=[case["requirement"]]
        if case["kind"] == "skill"
        else [],
        required_experience=[case["requirement"]]
        if case["kind"] == "experience"
        else [],
    )
    result = JobMatcher().match(resume, job)

    if case["kind"] == "skill":
        return (
            "match"
            if case["requirement"] in result.matched_skills
            else "no match",
            False,
        )
    if case["requirement"] in result.matched_experience_requirements:
        return "match", False
    if case["requirement"] in result.uncertain_experience_requirements:
        return "no match", True
    return "no match", False


def evaluation_metrics():
    metrics = {
        "cases": len(MATCHER_CASES),
        "true_positives": 0,
        "true_negatives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "uncertain": 0,
        "failed_cases": [],
    }
    for case in MATCHER_CASES:
        actual, uncertain = matcher_case_status(case)
        expected = case["expected"]
        metrics[
            {
                ("match", "match"): "true_positives",
                ("no match", "no match"): "true_negatives",
                ("match", "no match"): "false_positives",
                ("no match", "match"): "false_negatives",
            }[(actual, expected)]
        ] += 1
        if uncertain:
            metrics["uncertain"] += 1
        if actual != expected or uncertain != case.get("expected_uncertain", False):
            metrics["failed_cases"].append(case["name"])
    positive_predictions = metrics["true_positives"] + metrics["false_positives"]
    actual_positives = metrics["true_positives"] + metrics["false_negatives"]
    metrics["precision"] = (
        metrics["true_positives"] / positive_predictions
        if positive_predictions
        else 1.0
    )
    metrics["recall"] = (
        metrics["true_positives"] / actual_positives
        if actual_positives
        else 1.0
    )
    return metrics


@pytest.mark.parametrize("case", MATCHER_CASES, ids=lambda case: case["name"])
def test_curated_matcher_evaluation_cases(case):
    actual, uncertain = matcher_case_status(case)

    assert actual == case["expected"], case["rationale"]
    assert uncertain is case.get("expected_uncertain", False)


def test_curated_evaluation_confusion_metrics():
    metrics = evaluation_metrics()

    assert metrics["true_positives"] == 18
    assert metrics["true_negatives"] == 12
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 0
    assert metrics["uncertain"] == 1
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["failed_cases"] == []


def test_curated_evaluation_results_flow_through_ats_scorer():
    matcher = JobMatcher()
    scorer = ATSScorer(matcher)
    for case in MATCHER_CASES:
        if case["kind"] == "skill" and case["requirement"].startswith("AWS ("):
            resume = resume_for_case(case)
            job = JobRequirements(required_skills=[case["requirement"]])
            match = matcher.match(resume, job)
            result = scorer.score(resume, job, match, EXTRACTED_TEXT)
            for component in matcher.skill_requirement_components(
                case["requirement"]
            ):
                label = f"Required skill: {component}"
                if matcher.has_skill_evidence(resume, component):
                    assert label in result.matched_requirements, case["name"]
                else:
                    assert label in result.missing_requirements, case["name"]
            continue
        resume = resume_for_case(case)
        job = JobRequirements(
            required_skills=[case["requirement"]]
            if case["kind"] == "skill"
            else [],
            required_experience=[case["requirement"]]
            if case["kind"] == "experience"
            else [],
        )
        match = matcher.match(resume, job)
        result = scorer.score(resume, job, match, EXTRACTED_TEXT)
        label = (
            f"Required skill: {case['requirement']}"
            if case["kind"] == "skill"
            else f"Required experience: {case['requirement']}"
        )

        if case.get("expected_uncertain", False):
            assert any(label in item for item in result.uncertain_items), case["name"]
        elif case["expected"] == "match":
            assert label in result.matched_requirements, case["name"]
        else:
            assert label in result.missing_requirements, case["name"]
