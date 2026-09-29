from models.resume import Resume
from models.job import JobDescription
from models.job_match import JobMatch


class JobMatcher:

    SKILL_ALIASES = {
        "aws": {
            "aws",
            "aws cdk",
            "aws lambda",
            "amazon s3",
            "amazon sqs",
        },
        "javascript": {
            "javascript",
            "js",
        },
        "typescript": {
            "typescript",
            "ts",
        },
        "postgresql": {
            "postgresql",
            "postgres",
        },
    }

    def match(
    self,
    resume: Resume,
    job: JobDescription
    ) -> JobMatch:

        resume_skills = {
            self._normalize_skill(skill)
            for skill in resume.skills
        }

        matched_skills = []
        missing_skills = []

        for skill in job.required_skills:
            normalized_skill = self._normalize_skill(skill)

            if normalized_skill in resume_skills:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        matching_experience = self._find_matching_experience(
            resume,
            job.required_skills
        )

        missing_requirements = [
            f"Experience with {skill}"
            for skill in missing_skills
        ]

        summary = (
            f"Matched {len(matched_skills)} of "
            f"{len(job.required_skills)} required skills."
        )

        return JobMatch(
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matching_experience=matching_experience,
            missing_requirements=missing_requirements,
            summary=summary,
        )

    def _normalize_skill(self, skill: str) -> str:
        skill = skill.strip().lower()

        for canonical, aliases in self.SKILL_ALIASES.items():
            if skill in aliases:
                return canonical

        return skill

    def _has_skill(
        self,
        required_skill: str,
        resume_skills: set[str]
    ) -> bool:

        normalized_resume_skills = {
            self._normalize_skill(skill)
            for skill in resume_skills
        }

        return required_skill in normalized_resume_skills

    def _find_matching_experience(
        self,
        resume: Resume,
        required_skills: list[str]
    ) -> list[str]:

        matching_experience = []

        for experience in resume.experience:
            text = " ".join(
                experience.responsibilities
            ).lower()

            matched = [
                skill
                for skill in required_skills
                if skill.lower() in text
            ]

            if matched:
                matching_experience.append(
                    f"{experience.company} - "
                    f"{experience.role}: "
                    f"{', '.join(matched)}"
                )

        return matching_experience