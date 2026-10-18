from fastapi.testclient import TestClient
from google.genai import errors

import main
from models.job import JobRequirements


client = TestClient(main.app)


def test_match_job_parses_description_then_matches_resume(monkeypatch):
    parsed_descriptions = []

    def parse_job_description(description):
        parsed_descriptions.append(description)
        return JobRequirements(
            required_skills=["Java", "Spring Boot", "Kafka"],
            preferred_skills=["AWS"],
        )

    monkeypatch.setattr(
        main.llm_service,
        "parse_job_description",
        parse_job_description,
    )

    response = client.post(
        "/resume/match-job",
        json={
            "resume": {
                "name": "Jay",
                "skills": ["Java", "Spring Boot", "AWS"],
                "experience": [
                    {
                        "company": "Goldman Sachs",
                        "role": "Software Engineer",
                        "responsibilities": [
                            "Built backend services using Java and Spring Boot"
                        ],
                    }
                ],
            },
            "job_description": (
                "We need Java, Spring Boot and Kafka. AWS is preferred."
            ),
        },
    )

    assert response.status_code == 200
    assert parsed_descriptions == [
        "We need Java, Spring Boot and Kafka. AWS is preferred."
    ]
    result = response.json()
    assert result["matched_skills"] == ["Java", "Spring Boot"]
    assert result["missing_skills"] == ["Kafka"]
    assert result["matched_preferred_skills"] == ["AWS"]
    assert len(result["matching_experience"]) == 1


def test_match_job_returns_service_unavailable_on_gemini_server_error(
    monkeypatch,
):
    def fail_to_parse(_description):
        raise errors.ServerError(503, {"message": "internal provider detail"})

    monkeypatch.setattr(
        main.llm_service,
        "parse_job_description",
        fail_to_parse,
    )

    response = client.post(
        "/resume/match-job",
        json={"resume": {}, "job_description": "Java developer"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Job parsing service is temporarily unavailable. "
            "Please try again later."
        )
    }
    assert "internal provider detail" not in response.text


def test_match_job_rejects_missing_job_description():
    response = client.post("/resume/match-job", json={"resume": {}})

    assert response.status_code == 422