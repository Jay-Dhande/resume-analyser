
import calendar
import math
import re
from datetime import date, datetime, timedelta

from models.resume import Resume
from models.job import JobRequirements
from models.job_match import JobMatch


class JobMatcher:

    SKILL_ALIASES = {
        "kafka": ("apache kafka",),
        "dsa": (
            "data structures and algorithms",
            "data structure and algorithm",
        ),
        "concurrency": ("concurrent",),
        "unit testing": ("unit test", "unit tests"),
        "s3": ("aws s3", "amazon s3"),
        "lambda": ("aws lambda", "amazon lambda"),
        "sqs": ("aws sqs", "amazon sqs"),
        "relational database": (
            "relational databases",
            "relational database management system",
            "relational database management systems",
            "rdbms",
        ),
        "javascript": ("js",),
        "typescript": ("ts",),
        "postgresql": ("postgres",),
        "rest api": (
            "rest api development",
            "rest apis development",
            "rest apis",
        ),
    }
    DISTRIBUTED_SYSTEM_SKILL_ALIASES = {
        "distributed systems",
        "distributed system",
        "distributed caching",
        "distributed cache",
    }

    STOP_WORDS = {
        "a", "an", "and", "the", "with", "in", "of", "for", "to",
        "years", "year", "experience", "knowledge", "proficiency",
        "strong", "working", "familiarity", "ability", "plus",
        "preferred", "required",
        "development",
    }

    EXPERIENCE_TERM_ALIASES = {
        "system": ("systems",),
        "test": ("tests", "testing", "tested"),
        "backend": ("spring boot", "microservice", "microservices", "server-side"),
        "application": ("applications", "apps", "services", "service"),
        "develop": ("developed", "developing", "development", "built", "building"),
        "maintain": ("maintained", "maintaining", "maintenance"),
        "design": ("designed", "designing", "designs"),
        "integrate": ("integrated", "integrating", "integration", "integrations"),
        "diagnose": (
            "diagnosis", "debug", "debugged", "debugging",
            "diagnosed", "diagnosing", "troubleshoot", "troubleshooting",
            "troubleshot",
        ),
        "issue": (
            "issues", "problem", "problems", "failure", "failures",
            "incident", "incidents",
        ),
        "improve": ("improved", "improving", "improvements", "enhanced"),
        "performance": (
            "optimization", "optimizations", "optimized", "optimizing",
            "latency", "response times",
        ),
        "database": (
            "databases", "sql", "postgresql", "postgres", "mysql",
            "mariadb", "oracle", "sqlite", "sql server",
        ),
        "reliable": (
            "reliability", "reliably", "failure handling", "fault tolerance",
        ),
        "distributed": ("cross-application", "cross-app"),
        "api": ("apis", "rest endpoint", "rest endpoints"),
    }

    def match(self, resume: Resume, job: JobRequirements) -> JobMatch:
        matched_skills = []
        missing_skills = []

        for skill in job.required_skills:
            if self._has_skill_evidence(resume, skill):
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        matched_preferred_skills = []
        missing_preferred_skills = []

        for skill in job.preferred_skills:
            if self._has_skill_evidence(resume, skill):
                matched_preferred_skills.append(skill)
            else:
                missing_preferred_skills.append(skill)

        matched_experience_requirements = []
        missing_experience_requirements = []
        uncertain_experience_requirements = []

        for requirement in job.required_experience:
            status = self._experience_requirement_status(resume, requirement)
            if status is True:
                matched_experience_requirements.append(requirement)
            elif status is False:
                missing_experience_requirements.append(requirement)
            else:
                uncertain_experience_requirements.append(requirement)

        matched_preferred_experience = []
        missing_preferred_experience = []
        uncertain_preferred_experience_requirements = []

        for requirement in job.preferred_experience:
            status = self._experience_requirement_status(resume, requirement)
            if status is True:
                matched_preferred_experience.append(requirement)
            elif status is False:
                missing_preferred_experience.append(requirement)
            else:
                uncertain_preferred_experience_requirements.append(requirement)

        matching_experience = self._find_matching_experience(
            resume,
            job.required_skills,
            job.required_experience,
        )


        summary = (
            f"Matched {len(matched_skills)} of "
            f"{len(job.required_skills)} required skills."
        )

        return JobMatch(
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matched_preferred_skills=matched_preferred_skills,
            missing_preferred_skills=missing_preferred_skills,
            matching_experience=matching_experience,
            matched_experience_requirements=matched_experience_requirements,
            missing_experience_requirements=missing_experience_requirements,
            uncertain_experience_requirements=uncertain_experience_requirements,
            matched_preferred_experience=matched_preferred_experience,
            missing_preferred_experience=missing_preferred_experience,
            uncertain_preferred_experience_requirements=(
                uncertain_preferred_experience_requirements
            ),
            summary=summary,
        )

    def filter_supported_missing_requirements(
        self,
        resume: Resume,
        job_match: JobMatch,
    ) -> JobMatch:
        missing_experience = []
        uncertain_experience = list(
            job_match.uncertain_experience_requirements
        )
        matched_experience = list(job_match.matched_experience_requirements)
        for requirement in job_match.missing_experience_requirements:
            status = self._experience_requirement_status(resume, requirement)
            if status is True:
                matched_experience.append(requirement)
            elif status is False:
                missing_experience.append(requirement)
            else:
                uncertain_experience.append(requirement)

        missing_preferred_experience = []
        uncertain_preferred_experience = list(
            job_match.uncertain_preferred_experience_requirements
        )
        matched_preferred_experience = list(
            job_match.matched_preferred_experience
        )
        for requirement in job_match.missing_preferred_experience:
            status = self._experience_requirement_status(resume, requirement)
            if status is True:
                matched_preferred_experience.append(requirement)
            elif status is False:
                missing_preferred_experience.append(requirement)
            else:
                uncertain_preferred_experience.append(requirement)

        return job_match.model_copy(
            update={
                "missing_skills": [
                    skill for skill in job_match.missing_skills
                    if not self._has_skill_evidence(resume, skill)
                ],
                "missing_preferred_skills": [
                    skill for skill in job_match.missing_preferred_skills
                    if not self._has_skill_evidence(resume, skill)
                ],
                "matched_experience_requirements": matched_experience,
                "missing_experience_requirements": missing_experience,
                "uncertain_experience_requirements": uncertain_experience,
                "matched_preferred_experience": matched_preferred_experience,
                "missing_preferred_experience": missing_preferred_experience,
                "uncertain_preferred_experience_requirements": (
                    uncertain_preferred_experience
                ),
            }
        )

    def _normalize_skill(self, skill: str) -> str:
        normalized = re.sub(r"\s+", " ", skill.strip().lower())

        for canonical, aliases in self.SKILL_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                normalized = re.sub(
                    rf"(?<![\w+#]){re.escape(alias)}(?![\w+#])",
                    canonical,
                    normalized,
                )

        return normalized

    def skill_requirement_components(self, skill: str) -> list[str]:
        grouped_services = re.fullmatch(
            r"\s*aws\s*\(([^)]*)\)\s*",
            skill,
            re.IGNORECASE,
        )
        if not grouped_services:
            return [skill]

        return [
            component.strip()
            if re.match(r"\s*(?:aws|amazon)\b", component, re.IGNORECASE)
            else f"AWS {component.strip()}"
            for component in grouped_services.group(1).split(",")
            if component.strip()
        ]

    def skill_requirement_key(self, skill: str) -> str:
        normalized = self._normalize_skill(skill)
        if normalized in self.DISTRIBUTED_SYSTEM_SKILL_ALIASES:
            return "distributed systems"
        if normalized in {
            "sql", "postgresql", "mysql", "mariadb", "oracle", "sqlite",
            "rdbms", "relational database",
        }:
            return "relational database"
        return normalized

    def has_skill_evidence(self, resume: Resume, skill: str) -> bool:
        return self._has_skill_evidence(resume, skill)

    def experience_requirement_key(self, requirement: str) -> str:
        required_years = self._required_years(requirement)
        if required_years is not None:
            return f"tenure:{required_years:g}"
        return " ".join(sorted(self._requirement_keywords(requirement)))

    def experience_requirement_status(
        self,
        resume: Resume,
        requirement: str,
    ) -> bool | None:
        return self._experience_requirement_status(resume, requirement)

    def _skill_matches_evidence(self, skill: str, evidence: str) -> bool:
        normalized_skill = self._normalize_skill(skill)

        if normalized_skill in self.DISTRIBUTED_SYSTEM_SKILL_ALIASES:
            return bool(
                re.search(
                    r"\bdistributed\s+(?:systems?|cach(?:e|ing))\b",
                    evidence.lower(),
                )
            )

        if normalized_skill == "relational database":
            return bool(
                re.search(
                    r"\b(?:sql|postgresql|postgres|mysql|mariadb|oracle|sqlite|rdbms)\b",
                    evidence.lower(),
                )
            )

        if normalized_skill == "aws" and re.search(
            r"\b(?:aws|amazon web services)\b",
            evidence.lower(),
        ):
            return True

        normalized_evidence = self._normalize_skill(evidence)
        return bool(
            re.search(
                rf"(?<![\w+#]){re.escape(normalized_skill)}(?![\w+#])",
                normalized_evidence,
            )
        )

    def _has_skill_evidence(self, resume: Resume, skill: str) -> bool:
        evidence = list(resume.skills) + list(resume.projects)
        evidence.extend(resume.achievements)
        evidence.extend(
            evidence_item
            for experience in resume.experience
            for evidence_item in [experience.role or "", *experience.responsibilities]
        )
        grouped_services = re.fullmatch(
            r"\s*aws\s*\(([^)]*)\)\s*",
            skill,
            re.IGNORECASE,
        )
        if grouped_services:
            components = [
                component.strip()
                if re.match(r"\s*(?:aws|amazon)\b", component, re.IGNORECASE)
                else f"AWS {component.strip()}"
                for component in grouped_services.group(1).split(",")
                if component.strip()
            ]
            return bool(components) and all(
                any(self._skill_matches_evidence(component, item) for item in evidence)
                for component in components
            )

        return any(self._skill_matches_evidence(skill, item) for item in evidence)

    def _experience_text(self, experience) -> str:
        parts = [
            experience.company or "",
            experience.role or "",
            experience.location or "",
            " ".join(experience.responsibilities),
        ]
        return " ".join(parts).lower()

    def _requirement_keywords(self, requirement: str) -> set[str]:
        normalized = self._normalize_skill(requirement)
        aliases = sorted(
            (
                (alias, canonical)
                for canonical, terms in self.EXPERIENCE_TERM_ALIASES.items()
                for alias in terms
            ),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for alias, canonical in aliases:
            normalized = re.sub(
                rf"(?<![\w+#]){re.escape(alias)}(?![\w+#])",
                canonical,
                normalized,
            )
        words = re.findall(
            r"[a-zA-Z0-9+#.]+",
            normalized,
        )
        return {
            word for word in words
            if word not in self.STOP_WORDS and len(word) > 1
        }

    def _matches_experience_requirement(
        self,
        resume: Resume,
        requirement: str,
    ) -> bool:
        return self._experience_requirement_status(resume, requirement) is True

    def _experience_requirement_status(
        self,
        resume: Resume,
        requirement: str,
    ) -> bool | None:
        required_years = self._required_years(requirement)
        if required_years is not None:
            return self._has_required_tenure(resume, required_years)

        required_keywords = self._requirement_keywords(requirement)

        if not required_keywords:
            return False

        evidence = " ".join([
            self._experience_text(experience)
            for experience in resume.experience
        ] + resume.projects)
        if not evidence.strip():
            return None
        experience_keywords = self._requirement_keywords(evidence)
        overlap = required_keywords & experience_keywords
        threshold = max(1, math.ceil(len(required_keywords) * 0.75))

        return len(overlap) >= threshold

    def _required_years(self, requirement: str) -> float | None:
        match = re.search(
            r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:(?:-|\u2013|\u2014|to)\s*\d+(?:\.\d+)?|\+)?\s*(?:years?|yrs?)\b",
            requirement.lower(),
        )
        return float(match.group(1)) if match else None

    def _employment_date_range(
        self,
        value: str | None,
    ) -> tuple[date, date] | None:
        if not value or not value.strip():
            return None

        value = value.strip()
        if value.lower() in {"present", "current", "now"}:
            return None

        for date_format in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%B %Y", "%Y"):
            try:
                parsed = datetime.strptime(value, date_format).date()
            except ValueError:
                continue

            if date_format == "%Y":
                return date(parsed.year, 1, 1), date(parsed.year, 12, 31)
            if date_format != "%Y-%m-%d":
                last_day = calendar.monthrange(parsed.year, parsed.month)[1]
                return date(parsed.year, parsed.month, 1), date(
                    parsed.year, parsed.month, last_day
                )
            return parsed, parsed

        return None

    def _merged_interval_days(
        self,
        intervals: list[tuple[date, date]],
    ) -> int:
        if not intervals:
            return 0

        intervals.sort()
        start, end = intervals[0]
        total_days = 0
        for next_start, next_end in intervals[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                total_days += (end - start).days
                start, end = next_start, next_end
        return total_days + (end - start).days

    def _has_required_tenure(
        self,
        resume: Resume,
        required_years: float,
    ) -> bool | None:
        if not resume.experience:
            return None

        minimum_intervals = []
        maximum_intervals = []
        has_incomplete_dates = False
        today_exclusive = date.today() + timedelta(days=1)

        for experience in resume.experience:
            start_range = self._employment_date_range(experience.start_date)
            end_range = self._employment_date_range(experience.end_date)
            if not start_range:
                has_incomplete_dates = True
                continue

            if not end_range:
                has_incomplete_dates = True
                possible_end = max(start_range[0], today_exclusive)
                if start_range[0] < possible_end:
                    maximum_intervals.append((start_range[0], possible_end))
                continue

            if start_range[0] > end_range[1]:
                has_incomplete_dates = True
                continue

            minimum_start = start_range[1]
            minimum_end = end_range[0] + timedelta(days=1)
            if minimum_start < minimum_end:
                minimum_intervals.append((minimum_start, minimum_end))

            maximum_intervals.append(
                (start_range[0], end_range[1] + timedelta(days=1))
            )

        minimum_days = self._merged_interval_days(minimum_intervals)
        maximum_days = self._merged_interval_days(maximum_intervals)
        required_days = math.ceil(required_years * 365.2425)

        if minimum_days >= required_days:
            return True
        if not has_incomplete_dates and maximum_days < required_days:
            return False
        return None

    def _find_matching_experience(
        self,
        resume: Resume,
        required_skills: list[str],
        required_experience: list[str],
    ) -> list[str]:
        matching_experience = []

        for experience in resume.experience:
            text = self._experience_text(experience)

            matched_skills = [
                skill for skill in required_skills
                if self._skill_matches_evidence(skill, text)
            ]

            matched_requirements = [
                requirement for requirement in required_experience
                if self._matches_single_experience_text(
                    text, requirement
                )
            ]

            if matched_skills or matched_requirements:
                details = matched_skills + matched_requirements
                matching_experience.append(
                    f"{experience.company} - {experience.role}: "
                    f"{', '.join(details)}"
                )

        for project in resume.projects:
            matched_skills = [
                skill for skill in required_skills
                if self._skill_matches_evidence(skill, project)
            ]
            matched_requirements = [
                requirement for requirement in required_experience
                if self._matches_single_experience_text(project, requirement)
            ]
            if matched_skills or matched_requirements:
                details = matched_skills + matched_requirements
                matching_experience.append(
                    f"Project: {project}: {', '.join(details)}"
                )

        return matching_experience

    def _matches_single_experience_text(
        self,
        text: str,
        requirement: str,
    ) -> bool:
        required_keywords = self._requirement_keywords(requirement)

        if not required_keywords:
            return False

        experience_keywords = self._requirement_keywords(text)
        overlap = required_keywords & experience_keywords
        threshold = (len(required_keywords) + 1) // 2

        return len(overlap) >= threshold
