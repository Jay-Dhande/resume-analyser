from fastapi.testclient import TestClient
from google.genai import errors

import main
from models.suggestions import ImprovementSuggestion, ResumeSuggestions


client = TestClient(main.app)


def test_resume_suggestions_prioritize_missing_requirements(monkeypatch):
    received = {}
    mocked_response = ResumeSuggestions(
        suggestions=[
            ImprovementSuggestion(
                category="resume_quality",
                priority="medium",
                issue="The experience section lacks detail.",
                evidence="The analysis found a brief experience description.",
                recommendation="Expand the listed responsibilities with supported details.",
            ),
            ImprovementSuggestion(
                category="missing_required_experience",
                priority="high",
                issue="Required deployment experience is missing.",
                evidence="Deployment is listed in missing required experience.",
                recommendation="Add deployment experience only if supported by your work history.",
            ),
            ImprovementSuggestion(
                category="missing_required_skill",
                priority="high",
                issue="Kafka is a missing required skill.",
                evidence="Kafka is listed in missing required skills.",
                recommendation="If you have Kafka experience, include a supported example.",
            ),
        ]
    )

    def suggest_improvements(resume, analysis, job_match):
        received["resume"] = resume.name
        received["analysis"] = analysis.summary
        received["missing_skills"] = job_match.missing_skills
        return mocked_response

    monkeypatch.setattr(
        main.llm_service,
        "suggest_improvements",
        suggest_improvements,
    )

    response = client.post(
        "/resume/suggestions",
        json={
            "resume": {
                "name": "Jay",
                "skills": ["Java"],
            },
            "analysis": {
                "summary": "Experience descriptions could be more specific.",
                "experience": [
                    {
                        "category": "Experience",
                        "issue": "Experience descriptions are brief.",
                        "evidence": "One responsibility is listed.",
                        "suggestion": "Add detail where accurate.",
                        "severity": "medium",
                        "source": "llm",
                    }
                ],
            },
            "job_match": {
                "missing_skills": ["Kafka"],
                "missing_experience_requirements": [
                    "Deploy production services"
                ],
                "summary": "Matched 1 of 2 required skills.",
            },
        },
    )

    assert response.status_code == 200
    assert received == {
        "resume": "Jay",
        "analysis": "Experience descriptions could be more specific.",
        "missing_skills": ["Kafka"],
    }
    suggestions = response.json()["suggestions"]
    assert [suggestion["category"] for suggestion in suggestions] == [
        "missing_required_skill",
        "missing_required_experience",
        "resume_quality",
    ]
    assert suggestions[0]["recommendation"].startswith("If you have")


def test_resume_suggestions_returns_service_unavailable_on_gemini_error(
    monkeypatch,
):
    def fail_to_suggest(*_args):
        raise errors.ServerError(503, {"message": "internal provider detail"})

    monkeypatch.setattr(
        main.llm_service,
        "suggest_improvements",
        fail_to_suggest,
    )

    response = client.post(
        "/resume/suggestions",
        json={
            "resume": {},
            "analysis": {"summary": "No major issues found."},
            "job_match": {"summary": "Matched 0 of 0 required skills."},
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Resume suggestions service is temporarily unavailable. "
            "Please try again later."
        )
    }
    assert "internal provider detail" not in response.text


def test_resume_suggestions_rejects_invalid_request():
    response = client.post(
        "/resume/suggestions",
        json={"resume": {}, "analysis": {"summary": "No issues."}},
    )

    assert response.status_code == 422


def test_resume_suggestions_omits_skills_supported_by_resume(monkeypatch):
    received_missing_skills = {}

    def suggest_improvements(_resume, _analysis, job_match):
        received_missing_skills["required"] = job_match.missing_skills
        received_missing_skills["preferred"] = job_match.missing_preferred_skills
        return ResumeSuggestions()

    monkeypatch.setattr(
        main.llm_service,
        "suggest_improvements",
        suggest_improvements,
    )

    response = client.post(
        "/resume/suggestions",
        json={
            "resume": {
                "skills": [],
                "projects": ["Built a stream processor with Apache Kafka"],
            },
            "analysis": {"summary": "Resume reviewed."},
            "job_match": {
                "missing_skills": ["Kafka"],
                "missing_preferred_skills": ["Kafka"],
                "summary": "Matched 0 of 1 required skills.",
            },
        },
    )

    assert response.status_code == 200
    assert received_missing_skills == {"required": [], "preferred": []}
    assert response.json()["suggestions"] == []


def test_resume_suggestions_omit_supported_experience_and_preserve_tenure_uncertainty(
    monkeypatch,
):
    received_match = {}

    def suggest_improvements(_resume, _analysis, job_match):
        received_match.update(job_match.model_dump())
        return ResumeSuggestions()

    monkeypatch.setattr(
        main.llm_service,
        "suggest_improvements",
        suggest_improvements,
    )

    response = client.post(
        "/resume/suggestions",
        json={
            "resume": {
                "achievements": [
                    "Solved 800+ Data Structures and Algorithms problems"
                ],
                "experience": [
                    {
                        "role": "Software Engineer",
                        "responsibilities": [
                            "Developed and maintained Spring Boot services for backend applications"
                        ],
                    }
                ],
            },
            "analysis": {"summary": "Resume reviewed."},
            "job_match": {
                "missing_skills": ["DSA"],
                "missing_experience_requirements": [
                    "Developing and maintaining backend applications",
                    "1-3 years of experience",
                ],
                "summary": "Requirements need review.",
            },
        },
    )

    assert response.status_code == 200
    assert received_match["missing_skills"] == []
    assert received_match["missing_experience_requirements"] == []
    assert received_match["uncertain_experience_requirements"] == [
        "1-3 years of experience"
    ]