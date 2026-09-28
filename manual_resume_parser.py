from services.pdf_service import PDFService
from services.llm_service import LLMService


pdf_service = PDFService()
llm_service = LLMService()

resume_text = pdf_service.extract_text("resume.pdf")

resume = llm_service.parse_resume(resume_text)

print(resume.model_dump_json(indent=2))