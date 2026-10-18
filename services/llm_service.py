import os
import time

from google import genai
from google.genai import errors
from models.resume import Resume
from models.analysis import ResumeAnalysis
from dotenv import load_dotenv
from models.job import JobRequirements
from models.job_match import JobMatch
from models.suggestions import ResumeSuggestions

load_dotenv()


class LLMService:

    def __init__(self):
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )
        self.model = os.getenv("GEMINI_MODEL")
    
    def generate(self, prompt: str) -> str:
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )

                return response.text

            except errors.ServerError:
                if attempt == max_retries - 1:
                    raise

                time.sleep(2 ** attempt)
                
    def parse_resume(self, resume_text: str) -> Resume:
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=f"""
                Extract the resume information from the text below.

                Do not invent information.
                If information is missing, leave the field empty.

                Resume:
                {resume_text}
                """,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": Resume,
                    },
                )

                return Resume.model_validate_json(response.text)

            except errors.ServerError:
                if attempt == max_retries - 1:
                    raise

                time.sleep(2 ** attempt)
            
    def analyze_resume(self, resume: Resume) -> ResumeAnalysis:
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"""
            Rules:
            - Base your analysis only on information present in the resume.
            - Do not invent achievements, skills, experience, or missing information.
            - Every finding must include evidence from the resume.
            - Suggestions should be specific and actionable.
            - Do not assign an overall ATS score.
            - If something is already strong, do not invent an issue.
            - Do not treat PDF extraction artifacts as actual resume mistakes
            unless the extracted text clearly indicates a real issue.

            Resume:
            {resume.model_dump_json()}
            """,
            config={
                "response_mime_type": "application/json",
                "response_schema": ResumeAnalysis,
            },
        )

        analysis = ResumeAnalysis.model_validate_json(response.text)

        for category in [
            analysis.completeness,
            analysis.experience,
            analysis.skills,
            analysis.projects,
            analysis.ats,
        ]:
            for finding in category:
                finding.source = "llm"

        return analysis
    
    def parse_job_description(
        self,
        job_description: str
        ) -> JobRequirements:

        response = self.client.models.generate_content(
            model=self.model,
            contents=f"""
            Extract the requirements from this job description.

            Extract:
            - required technical skills
            - preferred technical skills
            - required experience
            - preferred experience

            Rules:
            - Only extract information explicitly present in the job description.
            - Do not invent requirements.
            - Keep skills concise and standardized.
            - If a category has no information, return an empty list.

            Job Description:
            {job_description}
            """,
            config={
                "response_mime_type": "application/json",
                "response_schema": JobRequirements,
            },
        )

        return JobRequirements.model_validate_json(response.text)

    def suggest_improvements(
        self,
        resume: Resume,
        analysis: ResumeAnalysis,
        job_match: JobMatch,
    ) -> ResumeSuggestions:
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"""
                        Create concise, actionable resume improvement suggestions using
                        only the facts in the supplied resume, analysis, and job match.

                        Rules:
                        - Never invent candidate skills, experience, achievements, or metrics.
                        - Use evidence from the supplied data for every suggestion.
                        - Do not phrase a missing skill or experience as something the
                            candidate already has. Recommend adding it only if the candidate
                            can truthfully support it; otherwise suggest emphasizing relevant
                            evidence that is actually present.
                        - First suggest missing required skills from job_match.missing_skills
                            with category "missing_required_skill".
                        - Next suggest missing required experience from
                            job_match.missing_experience_requirements with category
                            "missing_required_experience".
                        - Follow those with resume quality issues that are present in
                            analysis findings, using category "resume_quality".
                        - Do not create a suggestion for a missing requirement or quality
                            issue that is not present in the supplied data.
                        - Use high priority for missing required skills and experience.
                            For resume quality issues, use the finding's severity to choose
                            high, medium, or low.

                        Resume:
                        {resume.model_dump_json()}

                        Resume Analysis:
                        {analysis.model_dump_json()}

                        Job Match:
                        {job_match.model_dump_json()}
                        """,
            config={
                "response_mime_type": "application/json",
                "response_schema": ResumeSuggestions,
            },
        )

        return ResumeSuggestions.model_validate_json(response.text)