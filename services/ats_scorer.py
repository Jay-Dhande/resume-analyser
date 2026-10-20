import math
import re

from models.ats_score import ATSCategoryScore, ATSCompatibilityCheck, ATSScore
from models.job import JobRequirements
from models.job_match import JobMatch
from models.resume import Resume
from services.job_matcher import JobMatcher


class ATSScorer:
    CATEGORY_WEIGHTS = {
        "job_requirements": 70.0,
        "relevant_experience": 20.0,
        "ats_compatibility": 10.0,
    }
    REQUIRED_CRITERION_WEIGHT = 2.0
    PREFERRED_CRITERION_WEIGHT = 1.0
    MINIMUM_EXTRACTED_TEXT_CHARACTERS = 40
    MINIMUM_EXTRACTED_TEXT_WORDS = 8
    MINIMUM_RECOGNIZED_SECTIONS = 2

    def __init__(self, job_matcher: JobMatcher):
        self.job_matcher = job_matcher

    def score(
        self,
        resume: Resume,
        job_requirements: JobRequirements,
        job_match: JobMatch,
        extracted_text: str | None,
    ) -> ATSScore:
        skill_criteria = self._skill_criteria(resume, job_requirements, job_match)
        skill_keys = {criterion[3] for criterion in skill_criteria}
        experience_criteria = self._experience_criteria(
            resume,
            job_requirements,
            job_match,
            skill_keys,
        )
        compatibility_checks = self._compatibility_checks(
            resume,
            extracted_text,
        )

        matched_requirements = [
            criterion[0]
            for criterion in skill_criteria + experience_criteria
            if criterion[1] == "matched"
        ]
        missing_requirements = [
            criterion[0]
            for criterion in skill_criteria + experience_criteria
            if criterion[1] == "missing"
        ]
        uncertain_items = [
            f"{criterion[0]} (evidence is insufficient to assess)"
            for criterion in skill_criteria + experience_criteria
            if criterion[1] == "uncertain"
        ]
        uncertain_items.extend(
            f"{check.name}: {check.explanation}"
            for check in compatibility_checks
            if check.status == "uncertain"
        )

        category_scores = {
            "job_requirements": self._criterion_category_score(
                skill_criteria,
                self.CATEGORY_WEIGHTS["job_requirements"],
            ),
            "relevant_experience": self._criterion_category_score(
                experience_criteria,
                self.CATEGORY_WEIGHTS["relevant_experience"],
            ),
            "ats_compatibility": self._check_category_score(
                compatibility_checks,
                self.CATEGORY_WEIGHTS["ats_compatibility"],
            ),
        }

        job_criteria = skill_criteria + experience_criteria
        assessable_job_criteria = sum(
            criterion[1] != "uncertain" for criterion in job_criteria
        )
        available_points = sum(
            category.maximum_points for category in category_scores.values()
        )
        if not job_criteria or not assessable_job_criteria or not available_points:
            return ATSScore(
                overall_score=None,
                status="insufficient_data",
                category_scores=category_scores,
                matched_requirements=matched_requirements,
                missing_requirements=missing_requirements,
                uncertain_items=uncertain_items,
                compatibility_checks=compatibility_checks,
                calculation_summary=(
                    "No assessable job criterion is available; no overall score was calculated."
                ),
            )

        earned_points = sum(
            category.earned_points for category in category_scores.values()
        )
        overall_score = math.floor(
            earned_points / available_points * 100 + 0.5
        )
        uncertain_count = sum(
            criterion[1] == "uncertain" for criterion in job_criteria
        ) + sum(check.status == "uncertain" for check in compatibility_checks)
        summary = (
            "Category weights are job requirements 70%, relevant experience 20%, "
            "and verifiable ATS checks 10%. Required criteria weigh 2x preferred "
            "criteria. Uncertain items are excluded from earned and available points; "
            "available points are normalized to 100. "
            f"{len(matched_requirements)} criteria matched, "
            f"{len(missing_requirements)} were unsupported, and "
            f"{uncertain_count} were uncertain."
        )
        return ATSScore(
            overall_score=min(100, max(0, overall_score)),
            status="calculated",
            category_scores=category_scores,
            matched_requirements=matched_requirements,
            missing_requirements=missing_requirements,
            uncertain_items=uncertain_items,
            compatibility_checks=compatibility_checks,
            calculation_summary=summary,
        )

    def _skill_criteria(
        self,
        resume: Resume,
        requirements: JobRequirements,
        match: JobMatch,
    ) -> list[tuple[str, str, float, str]]:
        matched_keys = self._skill_keys(match.matched_skills)
        missing_keys = self._skill_keys(match.missing_skills)
        has_skill_context = bool(
            resume.skills
            or resume.projects
            or resume.achievements
            or any(
                experience.role or experience.responsibilities
                for experience in resume.experience
            )
        )
        criteria = []
        seen = set()

        for label, skills, weight in (
            ("Required skill", requirements.required_skills, self.REQUIRED_CRITERION_WEIGHT),
            ("Preferred skill", requirements.preferred_skills, self.PREFERRED_CRITERION_WEIGHT),
        ):
            for skill in skills:
                components = self.job_matcher.skill_requirement_components(skill)
                for component in components:
                    key = self.job_matcher.skill_requirement_key(component)
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    if len(components) > 1:
                        status = self._skill_status(
                            resume,
                            component,
                            has_skill_context,
                        )
                    elif key in matched_keys:
                        status = "matched"
                    elif key in missing_keys:
                        status = "missing" if has_skill_context else "uncertain"
                    else:
                        status = self._skill_status(
                            resume,
                            component,
                            has_skill_context,
                        )
                    criteria.append((f"{label}: {component}", status, weight, key))
        return criteria

    def _skill_status(
        self,
        resume: Resume,
        skill: str,
        has_skill_context: bool,
    ) -> str:
        if self.job_matcher.has_skill_evidence(resume, skill):
            return "matched"
        return "missing" if has_skill_context else "uncertain"

    def _skill_keys(self, skills: list[str]) -> set[str]:
        return {
            self.job_matcher.skill_requirement_key(component)
            for skill in skills
            for component in self.job_matcher.skill_requirement_components(skill)
        }

    def _experience_criteria(
        self,
        resume: Resume,
        requirements: JobRequirements,
        match: JobMatch,
        skill_keys: set[str],
    ) -> list[tuple[str, str, float, str]]:
        statuses = {}
        for values, status in (
            (match.matched_experience_requirements, "matched"),
            (match.missing_experience_requirements, "missing"),
            (match.uncertain_experience_requirements, "uncertain"),
            (match.matched_preferred_experience, "matched"),
            (match.missing_preferred_experience, "missing"),
            (match.uncertain_preferred_experience_requirements, "uncertain"),
        ):
            for requirement in values:
                statuses.setdefault(
                    self.job_matcher.experience_requirement_key(requirement),
                    status,
                )

        criteria = []
        seen = set(skill_keys)
        for label, values, weight in (
            (
                "Required experience",
                requirements.required_experience,
                self.REQUIRED_CRITERION_WEIGHT,
            ),
            (
                "Preferred experience",
                requirements.preferred_experience,
                self.PREFERRED_CRITERION_WEIGHT,
            ),
        ):
            for requirement in values:
                key = self.job_matcher.experience_requirement_key(requirement)
                if not key or key in seen:
                    continue
                seen.add(key)
                matched_status = statuses.get(key)
                result = self.job_matcher.experience_requirement_status(
                    resume,
                    requirement,
                )
                if result is None:
                    status = "uncertain"
                elif result is True or matched_status == "matched":
                    status = "matched"
                else:
                    status = "missing"
                criteria.append((f"{label}: {requirement}", status, weight, key))
        return criteria

    def _compatibility_checks(
        self,
        resume: Resume,
        extracted_text: str | None,
    ) -> list[ATSCompatibilityCheck]:
        if extracted_text is None:
            text_status = "uncertain"
            text_explanation = "Extracted PDF text was not provided."
        else:
            alphanumeric_count = len(re.findall(r"[A-Za-z0-9]", extracted_text))
            word_count = len(re.findall(r"\b\w+\b", extracted_text))
            has_meaningful_text = (
                alphanumeric_count >= self.MINIMUM_EXTRACTED_TEXT_CHARACTERS
                and word_count >= self.MINIMUM_EXTRACTED_TEXT_WORDS
            )
            text_status = "pass" if has_meaningful_text else "fail"
            text_explanation = (
                f"Extracted {alphanumeric_count} alphanumeric characters and "
                f"{word_count} words; meaningful text requires at least "
                f"{self.MINIMUM_EXTRACTED_TEXT_CHARACTERS} characters and "
                f"{self.MINIMUM_EXTRACTED_TEXT_WORDS} words."
            )

        sections = {
            "education": bool(resume.education),
            "experience": bool(resume.experience),
            "skills": bool(resume.skills),
            "projects": bool(resume.projects),
            "achievements": bool(resume.achievements),
        }
        recognized_count = sum(sections.values())
        sections_pass = recognized_count >= self.MINIMUM_RECOGNIZED_SECTIONS

        contact_present = bool(resume.email or resume.phone)
        employment_present = any(
            bool(experience.company or experience.role)
            and bool(
                experience.responsibilities
                or experience.start_date
                or experience.end_date
            )
            for experience in resume.experience
        )

        return [
            ATSCompatibilityCheck(
                name="meaningful_extracted_text",
                status=text_status,
                explanation=text_explanation,
            ),
            ATSCompatibilityCheck(
                name="recognized_resume_sections",
                status="pass" if sections_pass else "fail",
                explanation=(
                    f"Recognized {recognized_count} of {len(sections)} structured sections; "
                    f"at least {self.MINIMUM_RECOGNIZED_SECTIONS} are required."
                ),
            ),
            ATSCompatibilityCheck(
                name="contact_information",
                status="pass" if contact_present else "fail",
                explanation=(
                    "An email address or phone number is available."
                    if contact_present
                    else "No email address or phone number is available."
                ),
            ),
            ATSCompatibilityCheck(
                name="employment_information",
                status="pass" if employment_present else "fail",
                explanation=(
                    "At least one employment entry has an employer/role and supporting details."
                    if employment_present
                    else "No employment entry has an employer/role and dates or responsibilities."
                ),
            ),
        ]

    def _criterion_category_score(
        self,
        criteria: list[tuple[str, str, float, str]],
        category_weight: float,
    ) -> ATSCategoryScore:
        total_weight = sum(criterion[2] for criterion in criteria)
        assessed_weight = sum(
            criterion[2] for criterion in criteria
            if criterion[1] != "uncertain"
        )
        earned_weight = sum(
            criterion[2] for criterion in criteria
            if criterion[1] == "matched"
        )
        return ATSCategoryScore(
            earned_points=self._round_points(
                category_weight * earned_weight / total_weight
                if total_weight else 0
            ),
            maximum_points=self._round_points(
                category_weight * assessed_weight / total_weight
                if total_weight else 0
            ),
        )

    def _check_category_score(
        self,
        checks: list[ATSCompatibilityCheck],
        category_weight: float,
    ) -> ATSCategoryScore:
        assessed_checks = [check for check in checks if check.status != "uncertain"]
        if not checks:
            return ATSCategoryScore(earned_points=0, maximum_points=0)
        return ATSCategoryScore(
            earned_points=self._round_points(
                category_weight
                * sum(check.status == "pass" for check in checks)
                / len(checks)
            ),
            maximum_points=self._round_points(
                category_weight * len(assessed_checks) / len(checks)
            ),
        )

    def _round_points(self, points: float) -> float:
        return round(points + 1e-9, 2)