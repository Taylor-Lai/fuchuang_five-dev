import re
from pathlib import Path
from typing import List

from .base import DocumentChunk


class TxtParser:
    """
    TXT parser with paragraph-first chunking and sentence-aware splitting.
    Designed to preserve context with optional overlap and smoother boundaries.
    """

    def __init__(self, max_chunk_size: int = 500, overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def parse(self, file_path: str) -> List[DocumentChunk]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = self._normalize_newlines(text)
        filename = path.name

        paragraphs = self._split_by_paragraph(text)
        chunks = self._chunk_paragraphs(paragraphs)

        result: List[DocumentChunk] = []
        for i, content in enumerate(chunks):
            result.append(
                DocumentChunk.create(
                    content=content,
                    metadata={
                        "source": filename,
                        "file_type": "txt",
                        "chunk_index": i,
                    },
                )
            )
        return result

    def _split_by_paragraph(self, text: str) -> List[str]:
        """Split by blank lines (including lines with only whitespace)."""
        paras = re.split(r"\n\s*\n+", text)
        return [p.strip() for p in paras if p.strip()]

    def _chunk_paragraphs(self, paragraphs: List[str]) -> List[str]:
        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            if len(para) > self.max_chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_long_paragraph(para))
                continue

            candidate = para if not current else f"{current}\n\n{para}"
            if len(candidate) <= self.max_chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                current = para

        if current:
            chunks.append(current.strip())

        return self._apply_overlap(chunks)

    def _split_long_paragraph(self, text: str) -> List[str]:
        """
        Split long paragraph by sentence endings with overlap.
        Handles both Chinese and English punctuation.
        """
        sentence_endings = re.compile(r"(?<=[。！？；.!?;])\s+")
        sentences = sentence_endings.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: List[str] = []
        current = ""

        for sent in sentences:
            if not current:
                current = sent
                continue

            if len(current) + 1 + len(sent) <= self.max_chunk_size:
                current = f"{current} {sent}"
            else:
                chunks.append(current.strip())
                overlap_text = current[-self.overlap :] if self.overlap > 0 else ""
                if overlap_text and len(overlap_text) + 1 + len(sent) <= self.max_chunk_size:
                    current = f"{overlap_text} {sent}"
                else:
                    current = sent

        if current:
            chunks.append(current.strip())

        return chunks

    def _apply_overlap(self, chunks: List[str]) -> List[str]:
        if self.overlap <= 0 or len(chunks) <= 1:
            return chunks

        overlapped: List[str] = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            prev = overlapped[-1]
            prefix = prev[-self.overlap :] if len(prev) > self.overlap else prev
            if len(prefix) + 1 + len(chunk) <= self.max_chunk_size:
                overlapped.append(f"{prefix}\n{chunk}")
            else:
                overlapped.append(chunk)
        return overlapped

    def _normalize_newlines(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")
