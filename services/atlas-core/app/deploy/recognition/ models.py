from pydantic import BaseModel


class ApplicationRecognition(BaseModel):
    id: str
    name: str
    category: str
    confidence: float
    description: str