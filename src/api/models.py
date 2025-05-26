from pydantic import BaseModel


class APISpec(BaseModel):
    spec_content: str
    description: str | None = None
