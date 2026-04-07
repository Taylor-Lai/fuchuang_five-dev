import re
from pathlib import Path
from typing import Iterable, List, Tuple

from .base import DocumentChunk


class MarkdownParser:
    """
    Markdown parser with hierarchical headings + size-aware chunking.
    - Keeps heading context (full path) in each chunk for completeness.
    - Preserves code fences as atomic blocks when possible.
    - Splits long sections into smoother chunks with optional overlap.
    """

    def __init__(
        self,
        min_chunk_length: int = 30,
        max_chunk_size: int = 800,
        overlap: int = 80,
    ):
        self.min_chunk_length = min_chunk_length
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def parse(self, file_path: str) -> List[DocumentChunk]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = self._normalize_newlines(text)
        filename = path.name

        sections = self._split_by_headers(text)
        result: List[DocumentChunk] = []
        chunk_index = 0

        for heading_path, body in sections:
            chunks = self._chunk_section(body, heading_path)
            for content in chunks:
                if len(content) < self.min_chunk_length:
                    continue
                result.append(
                    DocumentChunk.create(
                        content=content,
                        metadata={
                            "source": filename,
                            "file_type": "md",
                            "chunk_index": chunk_index,
                            "heading": heading_path[-1].strip() if heading_path else "",
                            "heading_path": heading_path,
                        },
                    )
                )
                chunk_index += 1

        return result

    def _split_by_headers(self, text: str) -> List[Tuple[List[str], str]]:
        """
        Split markdown into sections by headings.
        Returns [(heading_path, body), ...] where heading_path is a list of headings.
        """
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(header_pattern.finditer(text))

        if not matches:
            return [([], text.strip())] if text.strip() else []

        sections: List[Tuple[List[str], str]] = []

        # Preamble before the first heading.
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(([], preamble))

        heading_stack: List[str] = []
        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading_line = match.group(0).strip()

            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading_line)

            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[body_start:body_end].strip()
            sections.append((heading_stack.copy(), body))

        return sections

    def _chunk_section(self, body: str, heading_path: List[str]) -> List[str]:
        if not body.strip() and not heading_path:
            return []

        blocks = list(self._split_blocks(body))
        if not blocks:
            content = self._format_with_heading(body.strip(), heading_path)
            return [content] if content else []

        chunks: List[str] = []
        current = ""

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # If a single block is too large, keep it as its own chunk.
            if len(block) > self.max_chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.append(block)
                continue

            candidate = block if not current else f"{current}\n\n{block}"
            if len(candidate) <= self.max_chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                current = block

        if current:
            chunks.append(current.strip())

        # Add optional overlap between adjacent chunks for smoother context.
        overlapped: List[str] = []
        for i, chunk in enumerate(chunks):
            if i == 0 or self.overlap <= 0:
                overlapped.append(chunk)
                continue
            prev = overlapped[-1]
            prefix = prev[-self.overlap :] if len(prev) > self.overlap else prev
            if len(prefix) + 1 + len(chunk) <= self.max_chunk_size:
                overlapped.append(f"{prefix}\n{chunk}")
            else:
                overlapped.append(chunk)

        return [self._format_with_heading(c, heading_path) for c in overlapped]

    def _split_blocks(self, text: str) -> Iterable[str]:
        """
        Split text into blocks while preserving fenced code blocks.
        Blocks are separated by blank lines outside code fences.
        """
        lines = text.split("\n")
        block_lines: List[str] = []
        in_code = False
        fence = ""

        for line in lines:
            stripped = line.strip()
            is_fence = stripped.startswith("```") or stripped.startswith("~~~")

            if in_code:
                block_lines.append(line)
                if is_fence and stripped.startswith(fence):
                    in_code = False
                    fence = ""
                continue

            if is_fence:
                if block_lines:
                    yield "\n".join(block_lines).strip()
                    block_lines = []
                in_code = True
                fence = stripped[:3]
                block_lines.append(line)
                continue

            if stripped == "":
                if block_lines:
                    yield "\n".join(block_lines).strip()
                    block_lines = []
                continue

            block_lines.append(line)

        if block_lines:
            yield "\n".join(block_lines).strip()

    def _format_with_heading(self, content: str, heading_path: List[str]) -> str:
        if not content:
            return ""
        if not heading_path:
            return content.strip()
        heading_block = "\n".join(heading_path)
        return f"{heading_block}\n{content}".strip()

    def _normalize_newlines(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")
