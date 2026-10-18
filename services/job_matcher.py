
import re

from models.resume import Resume
from models.job import JobRequirements
from models.job_match import JobMatch


class JobMatcher:

    SKILL_ALIASES = {
        "aws": {"aws", "aws cdk", "aws lambda", "amazon s3", "amazon sqs"},
        "javascript": {"javascript", "js"},
        "typescript": {"typescript", "ts"},
        "postgresql": {"postgresql", "postgres"},
    }

    STOP_WORDS = {
        "a", "an", "and", "the", "with", "in", "of", "for", "to",
        "years", "year", "experience", "knowledge", "proficiency",
        "strong", "working", "familiarity", "ability", "plus",
        "preferred", "required",
    }

    def match(self, resume: Resume, job: JobRequirements) -> JobMatch:
        resume_skills = {
            self._normalize_skill(skill)
            for skill in resume.skills
        }

        matched_skills = []
        missing_skills = []

        for skill in job.required_skills:
            if self._normalize_skill(skill) in resume_skills:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        matched_preferred_skills = []
        missing_preferred_skills = []

        for skill in job.preferred_skills:
            if self._normalize_skill(skill) in resume_skills:
                matched_preferred_skills.append(skill)
            else:
                missing_preferred_skills.append(skill)

        matched_experience_requirements = []
        missing_experience_requirements = []

        for requirement in job.required_experience:
            if self._matches_experience_requirement(resume, requirement):
                matched_experience_requirements.append(requirement)
            else:
                missing_experience_requirements.append(requirement)

        matched_preferred_experience = []
        missing_preferred_experience = []

        for requirement in job.preferred_experience:
            if self._matches_experience_requirement(resume, requirement):
                matched_preferred_experience.append(requirement)
            else:
                missing_preferred_experience.append(requirement)

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
            matched_preferred_experience=matched_preferred_experience,
            missing_preferred_experience=missing_preferred_experience,
            summary=summary,
        )

    def _normalize_skill(self, skill: str) -> str:
        skill = skill.strip().lower()

        for canonical, aliases in self.SKILL_ALIASES.items():
            if skill in aliases:
                return canonical

        return skill

    def _experience_text(self, experience) -> str:
        parts = [
            experience.company or "",
            experience.role or "",
            experience.location or "",
            " ".join(experience.responsibilities),
        ]
        return " ".join(parts).lower()

    def _requirement_keywords(self, requirement: str) -> set[str]:
        words = re.findall(r"[a-zA-Z0-9+#.]+", requirement.lower())
        return {
            word for word in words
            if word not in self.STOP_WORDS and len(word) > 1
        }

    def _matches_experience_requirement(
        self,
        resume: Resume,
        requirement: str,
    ) -> bool:
        required_keywords = self._requirement_keywords(requirement)

        if not required_keywords:
            return False

        for experience in resume.experience:
            text = self._experience_text(experience)
            experience_keywords = self._requirement_keywords(text)

            overlap = required_keywords & experience_keywords
            threshold = (len(required_keywords) + 1) // 2

            if len(overlap) >= threshold:
                return True

        return False

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
                if skill.lower() in text
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
