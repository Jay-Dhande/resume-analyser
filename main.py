from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile
from io import BytesIO

from services.llm_service import LLMService
from services.pdf_service import PDFService

load_dotenv()

app = FastAPI()

llm_service = LLMService()
pdf_service = PDFService()


class ChatRequest(BaseModel):
    prompt: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    response = llm_service.generate(request.prompt)

    return {"response": response}

@app.post("/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    contents = await file.read()

    resume_text = pdf_service.extract_text(BytesIO(contents))
    resume = llm_service.parse_resume(resume_text)

    return resume