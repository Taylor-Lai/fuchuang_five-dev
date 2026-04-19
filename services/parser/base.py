from pydantic import BaseModel
from typing import Optional
import uuid

class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: dict

    @staticmethod
    def create(content: str, metadata: dict) -> "DocumentChunk":
        return DocumentChunk(
            chunk_id=str(uuid.uuid4()),
            content=content.strip(),
            metadata=metadata
        )