
import json

from models.resume import Resume
from models.job import JobRequirements
from services.job_matcher import JobMatcher
from services.ats_scorer import ATSScorer


# Representative resume data based on your previously described experience.
# Contact details and extracted PDF text below are test placeholders.
resume = Resume(
    name="Jay Dhande",
    email="jay@example.com",
    phone="5551234567",
    education=[
        {
            "institution": "NIT Warangal",
            "degree": "B.Tech",
            "field": "Electrical and Electronics Engineering",
        }
    ],
    skills=[
        "C++",
        "Java",
        "Python",
        "Spring Boot",
        "REST APIs",
        "SQL",
        "Apache Kafka",
        "Redis",
        "MongoDB",
        "Snowflake",
        "Sybase IQ",
        "AWS CDK",
        "AWS Lambda",
        "AWS S3",
        "AWS SQS",
        "Docker",
        "CloudWatch",
        "Git",
        "Distributed Caching",
        "React",
        "Node.js",
    ],
    experience=[
        {
            "company": "Goldman Sachs",
            "role": "Software Engineer",
            "start_date": "2025-04-01",
            "end_date": "Present",
            "responsibilities": [
                "Migrated distributed caching workflows from Apache Ignite 2.16 to 3.1 using Java and Spring Boot",
                "Built a Snowflake ETL pipeline processing approximately 200 million rows daily from Sybase IQ",
                "Optimized SQL queries and caching workflows, reducing execution time and memory usage by approximately 25 percent",
                "Implemented scheduled AI commentary generation using Python and internal LLM APIs",
                "Built AWS infrastructure and data workflows using CDK, Lambda, SQS, S3, TypeScript, Python, and Docker",
                "Improved Lambda cold-start performance by approximately five times",
                "Enhanced a financial alerting system to prevent missed alerts",
            ],
        }
    ],
    projects=[
        "Notification service built with Spring Boot, Kafka, Redis, and Elasticsearch"
    ],
    achievements=[
        "Solved 800+ DSA problems and achieved contest rank 28 among 6000+ participants"
    ],
)

# Representative job requirements, not copied from a specific employer's JD.
requirements = JobRequirements(
    required_skills=[
        "Java",
        "Spring Boot",
        "REST API",
        "SQL",
        "Relational Databases",
        "Data Structures and Algorithms",
        "Multithreading",
        "Distributed Systems",
        "Unit Testing",
        "Debugging",
        "System Design",
    ],
    preferred_skills=[
        "Apache Kafka",
        "Redis",
        "AWS S3",
        "AWS Lambda",
        "AWS SQS",
        "Docker",
        "Python",
        "LLM APIs",
        "Kubernetes",
    ],
    required_experience=[
        "Backend development",
        "Database optimization",
        "Production issue diagnosis",
        "Distributed systems reliability",
    ],
)

# Placeholder text used only to exercise compatibility checks.
# This does NOT test extraction from your actual PDF.
extracted_text = """
Jay Dhande
Software Engineer
Email: jay@example.com
Phone: 5551234567

Professional Experience
Goldman Sachs
Software Engineer
Java, Spring Boot, Python, SQL, AWS, Kafka, Redis
Distributed caching migration, ETL pipelines, database optimization,
REST APIs, AI commentary generation, production financial alerting.

Education
B.Tech, Electrical and Electronics Engineering, NIT Warangal

Skills
Java, C++, Python, Spring Boot, SQL, AWS, Kafka, Redis, Docker

Projects
Notification Service using Spring Boot, Kafka, Redis and Elasticsearch

Achievements
Solved more than 800 data structures and algorithms problems.
"""

matcher = JobMatcher()
job_match = matcher.match(resume, requirements)

result = ATSScorer(matcher).score(
    resume,
    requirements,
    job_match,
    extracted_text,
)

print(json.dumps(result.model_dump(), indent=2, default=str))
