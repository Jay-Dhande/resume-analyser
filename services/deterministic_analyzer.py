from models.resume import Resume
from models.analysis import Finding


class DeterministicAnalyzer:

    def analyze(self, resume: Resume) -> list[Finding]:
        findings = []

        findings.extend(self._check_contact_info(resume))
        findings.extend(self._check_sections(resume))
        findings.extend(self._check_dates(resume))
        findings.extend(self._check_skills(resume))
        findings.extend(self._check_formatting(resume))

        return findings

    def _check_contact_info(self, resume: Resume) -> list[Finding]:
        findings = []

        if not resume.email:
            findings.append(
                Finding(
                    category="Contact",
                    issue="Email address is missing",
                    evidence="No email address found",
                    suggestion="Add a professional email address.",
                    severity="high",
                    source="deterministic",
                )
            )

        if not resume.phone:
            findings.append(
                Finding(
                    category="Contact",
                    issue="Phone number is missing",
                    evidence="No phone number found",
                    suggestion="Add a phone number if appropriate for the target role.",
                    severity="medium",
                    source="deterministic",
                )
            )

        return findings

    def _check_sections(self, resume: Resume) -> list[Finding]:
        findings = []

        if not resume.education:
            findings.append(
                Finding(
                    category="Completeness",
                    issue="Education section is missing",
                    evidence="No education entries found",
                    suggestion="Add your relevant educational qualifications.",
                    severity="medium",
                    source="deterministic",
                )
            )

        if not resume.experience:
            findings.append(
                Finding(
                    category="Completeness",
                    issue="Experience section is missing",
                    evidence="No experience entries found",
                    suggestion="Add relevant professional or internship experience.",
                    severity="high",
                    source="deterministic",
                )
            )

        if not resume.skills:
            findings.append(
                Finding(
                    category="Completeness",
                    issue="Skills section is missing",
                    evidence="No skills found",
                    suggestion="Add relevant technical and professional skills.",
                    severity="medium",
                    source="deterministic",
                )
            )

        return findings

    def _check_dates(self, resume: Resume) -> list[Finding]:
        findings = []

        for education in resume.education:
            if education.start_date and education.end_date:
                if education.start_date > education.end_date:
                    findings.append(
                        Finding(
                            category="Dates",
                            issue="Education dates appear inconsistent",
                            evidence=f"{education.start_date} - {education.end_date}",
                            suggestion="Verify the education start and end dates.",
                            severity="medium",
                            source="deterministic",
                        )
                    )

        return findings

    def _check_skills(self, resume: Resume) -> list[Finding]:
        findings = []

        normalized_skills = [skill.lower().strip() for skill in resume.skills]

        if len(normalized_skills) != len(set(normalized_skills)):
            findings.append(
                Finding(
                    category="Skills",
                    issue="Duplicate skills detected",
                    evidence="The skills list contains duplicate entries.",
                    suggestion="Remove duplicate skills from the skills section.",
                    severity="low",
                    source="deterministic",
                )
            )

        return findings
    def _check_formatting(self, resume: Resume) -> list[Finding]:
        findings = []

        text = " ".join(
            responsibility
            for experience in resume.experience
            for responsibility in experience.responsibilities
        )

        artifacts = [
            "fromApache",
            "usingJava",
            "usingPython",
            "Pythonand",
            "onAWSusing",
            "pipelinefor",
            "by5x",
            "modelused",
            "˜",
        ]

        found = [artifact for artifact in artifacts if artifact in text]

        if found:
            findings.append(
                Finding(
                    category="Formatting",
                    issue="PDF text extraction produced formatting artifacts",
                    evidence=", ".join(found),
                    suggestion="Review spacing and special characters in the original PDF.",
                    severity="medium",
                    source="deterministic",
                )
            )

        return findings