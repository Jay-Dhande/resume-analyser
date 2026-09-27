from services.pdf_service import PDFService

service = PDFService()

text = service.extract_text("resume.pdf")

print(text)