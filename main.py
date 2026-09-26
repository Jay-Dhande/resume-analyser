from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from services.llm_service import LLMService

load_dotenv()

app = FastAPI()

llm_service = LLMService()


class ChatRequest(BaseModel):
    prompt: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    response = llm_service.generate(request.prompt)

    return {"response": response}