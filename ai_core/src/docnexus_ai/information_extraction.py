"""Chunked information extraction for unstructured documents."""

from __future__ import annotations

import traceback
import re
from pathlib import Path

from docx import Document
from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field, create_model

from docnexus_ai.llm import get_chat_llm

def _schema_classes():
    try:
        from ai_core.engine.schemas import Mod2_ExtractOutput
    except ImportError:  # pragma: no cover - compatibility for tests importing engine directly
        from engine.schemas import Mod2_ExtractOutput
    return Mod2_ExtractOutput

EXTRACTION_CHUNK_SIZE = 6000
EXTRACTION_CHUNK_OVERLAP = 500
DATE_RE = re.compile(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?")
NUMBER_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def chunk_text(text: str, chunk_size: int = EXTRACTION_CHUNK_SIZE, overlap: int = EXTRACTION_CHUNK_OVERLAP) -> list[dict[str, object]]:
    if not text:
        return [{"chunk_id": 0, "start": 0, "end": 0, "text": ""}]
    chunks: list[dict[str, object]] = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({"chunk_id": chunk_id, "start": start, "end": end, "text": text[start:end]})
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        chunk_id += 1
    return chunks


def is_missing_extraction_value(value: object) -> bool:
    return value is None or str(value).strip() in {"", "未找到", "null", "None"}


def find_evidence_snippet(text: str, value: object, window: int = 80) -> str | None:
    if is_missing_extraction_value(value):
        return None
    needle = str(value).strip()
    if not needle:
        return None
    index = text.find(needle)
    if index < 0:
        return None
    start = max(index - window, 0)
    end = min(index + len(needle) + window, len(text))
    return text[start:end].replace("\n", " ").strip()


def normalize_field_value(field_name: str, value: object) -> object:
    if is_missing_extraction_value(value):
        return "未找到"
    text = str(value).strip()
    normalized_name = "".join(field_name.split()).lower()
    date_match = DATE_RE.search(text)
    if date_match and any(token in normalized_name for token in ("日期", "时间", "date", "time")):
        year, month, day = date_match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    if any(token in normalized_name for token in ("金额", "预算", "数量", "人口", "gdp", "收入", "病例", "检测")):
        number_match = NUMBER_RE.search(text.replace(",", ""))
        if number_match:
            number_text = number_match.group(0)
            try:
                return float(number_text) if "." in number_text else int(number_text)
            except ValueError:
                return text
    return text


def infer_field_type(field_name: str, value: object) -> str:
    normalized_name = "".join(field_name.split()).lower()
    if any(token in normalized_name for token in ("日期", "时间", "date", "time")):
        return "date"
    if any(token in normalized_name for token in ("金额", "预算", "数量", "人口", "gdp", "收入", "病例", "检测", "比例", "率")):
        return "number"
    if is_missing_extraction_value(value):
        return "unknown"
    return "text"


def validate_field_value(field_name: str, raw_value: object, normalized_value: object, confidence: float, conflicts: dict[str, list[object]]) -> dict[str, object]:
    expected_type = infer_field_type(field_name, raw_value)
    if is_missing_extraction_value(raw_value):
        status = "missing"
    elif field_name in conflicts:
        status = "conflict"
    elif confidence < 0.6:
        status = "low_confidence"
    elif expected_type == "number" and not isinstance(normalized_value, (int, float)):
        status = "type_mismatch"
    elif expected_type == "date" and not (isinstance(normalized_value, str) and DATE_RE.search(str(raw_value))):
        status = "type_mismatch"
    else:
        status = "pass"
    return {
        "status": status,
        "expected_type": expected_type,
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "confidence": confidence,
    }


def merge_chunk_extractions(
    chunk_results: list[dict[str, object]],
    chunks: list[dict[str, object]],
    target_entities: list[str],
    full_text: str,
) -> dict[str, object]:
    merged: dict[str, object] = {entity: "未找到" for entity in target_entities}
    evidence: dict[str, dict[str, object]] = {}
    conflicts: dict[str, list[object]] = {}
    normalized_values: dict[str, object] = {}
    confidence: dict[str, float] = {}
    candidates: dict[str, list[object]] = {}
    validation: dict[str, dict[str, object]] = {}

    for chunk, result in zip(chunks, chunk_results):
        for entity in target_entities:
            value = result.get(entity)
            if is_missing_extraction_value(value):
                continue
            current = merged.get(entity)
            if is_missing_extraction_value(current):
                merged[entity] = value
                evidence[entity] = {
                    "chunk_id": chunk["chunk_id"],
                    "char_range": [chunk["start"], chunk["end"]],
                    "snippet": find_evidence_snippet(str(chunk["text"]), value),
                }
            elif value != current:
                conflicts.setdefault(entity, [current])
                if value not in conflicts[entity]:
                    conflicts[entity].append(value)
            candidates.setdefault(entity, [])
            if value not in candidates[entity]:
                candidates[entity].append(value)

    for entity in target_entities:
        value = merged.get(entity)
        normalized_values[entity] = normalize_field_value(entity, value)
        if is_missing_extraction_value(value):
            confidence[entity] = 0.0
        elif entity in conflicts:
            confidence[entity] = 0.55
        elif evidence.get(entity, {}).get("snippet"):
            confidence[entity] = 0.9
        else:
            confidence[entity] = 0.7
        validation[entity] = validate_field_value(
            entity,
            value,
            normalized_values[entity],
            confidence[entity],
            conflicts,
        )

    found_count = sum(1 for entity in target_entities if not is_missing_extraction_value(merged.get(entity)))
    merged["_meta"] = {
        "strategy": "chunked_structured_llm_extraction",
        "chunk_count": len(chunks),
        "text_length": len(full_text),
        "target_field_count": len(target_entities),
        "found_field_count": found_count,
        "coverage": round(found_count / len(target_entities), 4) if target_entities else 0,
        "evidence": evidence,
        "conflicts": conflicts,
        "normalized": normalized_values,
        "confidence": confidence,
        "candidates": candidates,
        "validation": validation,
    }
    return merged


def _read_document_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if file_path.endswith(".xlsx"):
        import pandas as pd

        df = pd.read_excel(file_path)
        return df.to_markdown(index=False)

    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {file_path}")


def handle_information_extraction(input_data):
    Mod2_ExtractOutput = _schema_classes()
    try:
        full_text = _read_document_text(input_data.file_path)
        fields_spec = {
            entity: (str, Field(default="未找到", description=f"提取 '{entity}' 的内容"))
            for entity in input_data.target_entities
        }
        dynamic_model = create_model("DynamicExtractionModel", **fields_spec)
        chunks = chunk_text(full_text)

        structured_llm = get_chat_llm().with_structured_output(dynamic_model)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一个精准的信息提取 AI。请只基于当前文本片段提取指定字段，以 JSON 格式输出。"
                "如果当前片段没有找到某个字段，请填'未找到'。不要编造，不要跨片段推测。\n\n"
                "当前片段：\n{text}",
            ),
            ("human", "请提取以下字段：{entities}"),
        ])

        chunk_results: list[dict[str, object]] = []
        for chunk in chunks:
            result = (prompt | structured_llm).invoke({
                "text": chunk["text"],
                "entities": ", ".join(input_data.target_entities),
            })
            chunk_results.append({} if result is None else result.model_dump())

        extracted_data = merge_chunk_extractions(chunk_results, chunks, input_data.target_entities, full_text)
        return Mod2_ExtractOutput(status="success", extracted_data=extracted_data)

    except Exception:
        return Mod2_ExtractOutput(status="failed", message=traceback.format_exc())
