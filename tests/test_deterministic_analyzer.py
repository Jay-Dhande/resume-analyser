from models.resume import Resume
from services.deterministic_analyzer import DeterministicAnalyzer


def test_missing_email():
    resume = Resume(
        name="Test User",
        phone="1234567890",
        skills=["Python"],
    )

    analyzer = DeterministicAnalyzer()

    findings = analyzer.analyze(resume)

    assert any(
        finding.issue == "Email address is missing"
        for finding in findings
    )


def test_duplicate_skills():
    resume = Resume(
        name="Test User",
        skills=["Python", "Java", "python"],
    )

    analyzer = DeterministicAnalyzer()

    findings = analyzer.analyze(resume)

    assert any(
        finding.issue == "Duplicate skills detected"
        for finding in findings
    )


def test_pdf_artifact():
    resume = Resume(
        name="Test User",
        experience=[
            {
                "company": "Test",
                "role": "Engineer",
                "responsibilities": [
                    "Worked withApache Ignite usingPythonand AWS"
                ],
            }
        ],
    )

    analyzer = DeterministicAnalyzer()

    findings = analyzer.analyze(resume)

    assert any(
        finding.category == "Formatting"
        for finding in findings
    )