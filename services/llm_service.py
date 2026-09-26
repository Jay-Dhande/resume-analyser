import os

from google import genai
from google.genai import errors



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