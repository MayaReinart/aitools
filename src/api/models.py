from fastapi import UploadFile
from pydantic import BaseModel


class SpecUpload(BaseModel):
    file: UploadFile
