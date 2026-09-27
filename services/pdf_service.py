from pypdf import PdfReader


class PDFService:

    def extract_text(self, file) -> str:
        reader = PdfReader(file)

        text = []

        for page in reader.pages:
            text.append(page.extract_text() or "")

        return "\n".join(text)