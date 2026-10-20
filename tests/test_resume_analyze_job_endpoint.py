from fastapi.testclient import TestClient
from google.genai import errors
import httpx

import main
from models.analysis import ResumeAnalysis
from models.job import JobRequirements
from models.resume import Resume
from models.suggestions import ResumeSuggestions


client = TestClient(main.app)


def test_analyze_job_runs_existing_pipeline(monkeypatch):
    calls = []
    resume = Resume(name="Jay", skills=["Java"])
    analysis = ResumeAnalysis(summary="Resume reviewed.")
    requirements = JobRequirements(required_skills=["Java", "Kafka"])
    suggestions = ResumeSuggestions()

    def extract_text(_file):
        calls.append("extract_pdf")
        return "resume text"

    def parse_resume(resume_text):
        calls.append(("parse_resume", resume_text))
        return resume

    def analyze_resume(parsed_resume):
        calls.append(("analyze_resume", parsed_resume))
        return analysis

    def parse_job_description(description):
        calls.append(("parse_job", description))
        return requirements

    def suggest_improvements(parsed_resume, parsed_analysis, job_match):
        calls.append(("suggest", parsed_resume, parsed_analysis, job_match))
        return suggestions

    monkeypatch.setattr(main.pdf_service, "extract_text", extract_text)
    monkeypatch.setattr(main.llm_service, "parse_resume", parse_resume)
    monkeypatch.setattr(main.llm_service, "analyze_resume", analyze_resume)
    monkeypatch.setattr(
        main.llm_service,
        "parse_job_description",
        parse_job_description,
    )
    monkeypatch.setattr(
        main.llm_service,
        "suggest_improvements",
        suggest_improvements,
    )

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java and Kafka required"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["resume"]["name"] == "Jay"
    assert result["analysis"]["summary"] == "Resume reviewed."
    assert result["job_requirements"]["required_skills"] == ["Java", "Kafka"]
    assert result["job_match"]["matched_skills"] == ["Java"]
    assert result["job_match"]["missing_skills"] == ["Kafka"]
    assert result["suggestions"]["suggestions"] == []
    assert result["ats_score"]["status"] == "calculated"
    assert 0 <= result["ats_score"]["overall_score"] <= 100
    assert set(result) == {
        "resume",
        "analysis",
        "job_requirements",
        "job_match",
        "suggestions",
        "ats_score",
    }
    assert [call[0] if isinstance(call, tuple) else call for call in calls] == [
        "extract_pdf",
        "parse_resume",
        "analyze_resume",
        "parse_job",
        "suggest",
    ]


def test_analyze_job_rejects_invalid_pdf():
    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file is not a valid or readable PDF."
    }


def test_analyze_job_handles_invalid_structured_resume(monkeypatch, caplog):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")

    def fail_to_parse(_text):
        Resume.model_validate({"skills": "not a list"})

    monkeypatch.setattr(main.llm_service, "parse_resume", fail_to_parse)

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The resume parsing service returned an invalid response."
    }
    assert "Invalid structured resume response" in caplog.text


def test_analyze_job_logs_parse_provider_failure(monkeypatch, caplog):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")

    def fail_to_parse(_text):
        raise errors.ServerError(503, {"message": "private parse details"})

    monkeypatch.setattr(main.llm_service, "parse_resume", fail_to_parse)

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 503
    assert "private parse details" not in response.text
    assert "Resume parsing step failed" in caplog.text


def test_analyze_job_returns_service_unavailable_on_provider_failure(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )

    def fail_analysis(_resume):
        raise errors.ServerError(503, {"message": "private provider details"})

    monkeypatch.setattr(main.llm_service, "analyze_resume", fail_analysis)

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Resume analysis service is temporarily unavailable. "
            "Please try again later."
        )
    }
    assert "private provider details" not in response.text
    assert "Gemini API request failed" in caplog.text


def test_analyze_job_returns_quota_error_and_retry_delay(monkeypatch, caplog):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )

    provider_error = errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "private quota response details",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "43200s",
                    }
                ],
            }
        },
    )

    calls = []

    def fail_analysis(_resume):
        calls.append("analysis")
        raise provider_error

    monkeypatch.setattr(main.llm_service, "analyze_resume", fail_analysis)

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "43200"
    assert "quota or rate limit reached" in response.json()["detail"]
    assert "43200 seconds" in response.json()["detail"]
    assert "private quota response details" not in response.text
    assert "Gemini quota/rate limit reached" in caplog.text
    assert "retry_after_seconds=43200" in caplog.text
    assert calls == ["analysis"]


def test_analyze_job_handles_quota_error_without_retry_delay(monkeypatch):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )
    monkeypatch.setattr(
        main.llm_service,
        "analyze_resume",
        lambda _resume: (_ for _ in ()).throw(
            errors.ClientError(
                429,
                {"error": {"code": 429, "message": "quota exhausted"}},
            )
        ),
    )

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 429
    assert "Retry-After" not in response.headers
    assert "Retry after quota becomes available" in response.json()["detail"]
    assert "quota exhausted" not in response.text


def test_analyze_job_uses_numeric_retry_after_header(monkeypatch):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )
    provider_error = errors.ClientError(
        429,
        {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}},
        response=httpx.Response(429, headers={"Retry-After": "90"}),
    )
    monkeypatch.setattr(
        main.llm_service,
        "analyze_resume",
        lambda _resume: (_ for _ in ()).throw(provider_error),
    )

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "90"
    assert "90 seconds" in response.json()["detail"]


def test_analyze_job_detects_resource_exhausted_status_without_429(
    monkeypatch,
):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )
    monkeypatch.setattr(
        main.llm_service,
        "analyze_resume",
        lambda _resume: (_ for _ in ()).throw(
            errors.ClientError(
                400,
                {
                    "error": {
                        "code": 400,
                        "status": "RESOURCE_EXHAUSTED",
                        "message": "quota exhausted",
                    }
                },
            )
        ),
    )

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 429
    assert "quota or rate limit reached" in response.json()["detail"]


def test_analyze_job_keeps_non_quota_client_errors_on_service_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )
    monkeypatch.setattr(
        main.llm_service,
        "analyze_resume",
        lambda _resume: (_ for _ in ()).throw(
            errors.ClientError(
                400,
                {"error": {"code": 400, "message": "private invalid request"}},
            )
        ),
    )

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    assert "private invalid request" not in response.text


def test_analyze_job_logs_and_sanitizes_network_failure(monkeypatch, caplog):
    monkeypatch.setattr(main.pdf_service, "extract_text", lambda _file: "text")
    monkeypatch.setattr(
        main.llm_service,
        "parse_resume",
        lambda _text: Resume(name="Jay"),
    )

    def fail_analysis(_resume):
        raise httpx.ConnectError("simulated private network detail")

    monkeypatch.setattr(main.llm_service, "analyze_resume", fail_analysis)

    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
        data={"job_description": "Java role"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Resume analysis service is temporarily unavailable. "
            "Please try again later."
        )
    }
    assert "simulated private network detail" not in response.text
    assert "Network request failed" in caplog.text


def test_analyze_job_validates_required_multipart_fields():
    response = client.post(
        "/resume/analyze-job",
        files={"file": ("resume.pdf", b"fake pdf bytes", "application/pdf")},
    )

    assert response.status_code == 422