from pathlib import Path
from typing import Dict, List, Tuple
import base64
import hashlib

from docx import Document

from .base import DocumentChunk

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class DocxParser:
    """
    Word parser.
    Strategy:
    - Split by heading paragraphs.
    - Keep tables as standalone chunks.
    - Extract images as standalone chunks (base64 content + image metadata).
    """

    def __init__(self, min_chunk_length: int = 30):
        self.min_chunk_length = min_chunk_length

    def parse(self, file_path: str) -> List[DocumentChunk]:
        path = Path(file_path)
        doc = Document(str(path))
        filename = path.name

        segments = self._extract_segments(doc)
        result: List[DocumentChunk] = []
        chunk_index = 0

        for seg in segments:
            seg_type = seg[0]
            heading = seg[1]
            content = seg[2]
            extra = seg[3] if len(seg) > 3 else {}

            if seg_type == "image":
                metadata = {
                    "source": filename,
                    "file_type": "docx",
                    "chunk_index": chunk_index,
                    "heading": heading,
                    "segment_type": "image",
                    **extra,
                }
                result.append(DocumentChunk.create(content=content, metadata=metadata))
                chunk_index += 1
                continue

            if len(content.strip()) < self.min_chunk_length:
                continue

            result.append(
                DocumentChunk.create(
                    content=content.strip(),
                    metadata={
                        "source": filename,
                        "file_type": "docx",
                        "chunk_index": chunk_index,
                        "heading": heading,
                        "segment_type": seg_type,
                    },
                )
            )
            chunk_index += 1

        return result

    def _extract_segments(self, doc: Document) -> List[Tuple]:
        """
        Return segments in source order:
        - ("text", heading, content)
        - ("table", heading, content)
        - ("image", heading, content, extra)
        """
        segments: List[Tuple] = []
        current_heading = ""
        current_buffer: List[str] = []
        image_map = self._build_image_map(doc)

        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1]

            if tag == "p":
                tokens = self._parse_paragraph_tokens(child)
                style_name = self._get_style_name(child)
                is_heading = style_name.lower().startswith("heading") or style_name in ["1", "2", "3", "4", "5"]
                para_text = "".join(v for t, v in tokens if t == "text").strip()

                if is_heading and para_text:
                    if current_buffer:
                        segments.append(("text", current_heading, "\n".join(current_buffer)))
                        current_buffer = []
                    current_heading = para_text

                    for token_type, value in tokens:
                        if token_type != "image":
                            continue
                        if value not in image_map:
                            continue
                        img_bytes, content_type = image_map[value]
                        segments.append(self._make_image_chunk(current_heading, img_bytes, content_type, value))
                    continue

                para_text_buffer = ""
                for token_type, value in tokens:
                    if token_type == "text":
                        para_text_buffer += value
                        continue

                    if para_text_buffer.strip():
                        current_buffer.append(para_text_buffer.strip())
                        para_text_buffer = ""

                    if value in image_map:
                        if current_buffer:
                            segments.append(("text", current_heading, "\n".join(current_buffer)))
                            current_buffer = []
                        img_bytes, content_type = image_map[value]
                        segments.append(self._make_image_chunk(current_heading, img_bytes, content_type, value))

                if para_text_buffer.strip():
                    current_buffer.append(para_text_buffer.strip())

            elif tag == "tbl":
                if current_buffer:
                    segments.append(("text", current_heading, "\n".join(current_buffer)))
                    current_buffer = []

                table_text = self._extract_table(child)
                if table_text.strip():
                    segments.append(("table", current_heading, table_text))

                table_images = self._extract_images_from_element(child, image_map, current_heading)
                segments.extend(table_images)

        if current_buffer:
            segments.append(("text", current_heading, "\n".join(current_buffer)))

        return segments

    def _build_image_map(self, doc: Document) -> Dict[str, Tuple[bytes, str]]:
        image_map: Dict[str, Tuple[bytes, str]] = {}
        for rid, rel in doc.part.rels.items():
            if "image" not in rel.reltype:
                continue
            try:
                image_map[rid] = (rel.target_part.blob, rel.target_part.content_type)
            except Exception:
                continue
        return image_map

    def _parse_paragraph_tokens(self, para_elem) -> List[Tuple[str, str]]:
        """
        Return tokens in source order:
        - ("text", text)
        - ("image", rid)
        """
        tokens: List[Tuple[str, str]] = []
        for elem in para_elem.iter():
            local = elem.tag.split("}")[-1]
            if local == "t":
                tokens.append(("text", elem.text or ""))
            elif local == "blip":
                embed = elem.get(f"{{{R_NS}}}embed")
                if embed:
                    tokens.append(("image", embed))
        return tokens

    def _extract_images_from_element(self, element, image_map: Dict[str, Tuple[bytes, str]], heading: str) -> List[Tuple]:
        image_segments: List[Tuple] = []
        for elem in element.iter():
            if elem.tag.split("}")[-1] != "blip":
                continue
            embed = elem.get(f"{{{R_NS}}}embed")
            if not embed or embed not in image_map:
                continue
            img_bytes, content_type = image_map[embed]
            image_segments.append(self._make_image_chunk(heading, img_bytes, content_type, embed))
        return image_segments

    def _make_image_chunk(self, heading: str, img_bytes: bytes, content_type: str, rid: str) -> Tuple:
        ext = content_type.split("/")[-1].replace("jpeg", "jpg")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        img_hash = hashlib.md5(img_bytes).hexdigest()[:8]
        content = f"[IMAGE:{ext}]\n{b64}"
        extra = {
            "image_format": ext,
            "image_size_bytes": len(img_bytes),
            "image_hash": img_hash,
            "image_rid": rid,
        }
        return ("image", heading, content, extra)

    def _get_style_name(self, para_elem) -> str:
        ns = para_elem.nsmap.get("w", W_NS)
        ppr = para_elem.find(f"{{{ns}}}pPr")
        if ppr is None:
            return ""
        pstyle = ppr.find(f"{{{ns}}}pStyle")
        if pstyle is None:
            return ""
        return pstyle.get(f"{{{ns}}}val", "")

    def _extract_table(self, tbl_element) -> str:
        rows: List[str] = []
        for tr in tbl_element.findall(f"{{{W_NS}}}tr"):
            cells: List[str] = []
            for tc in tr.findall(f"{{{W_NS}}}tc"):
                cell_text = "".join(t.text or "" for t in tc.iter() if t.tag == f"{{{W_NS}}}t").strip()
                cells.append(cell_text)
            if any(cells):
                rows.append(" | ".join(cells))
        return "[TABLE]\n" + "\n".join(rows)
