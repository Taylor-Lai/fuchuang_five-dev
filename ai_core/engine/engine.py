"""Backward-compatible AI engine facade.

The backend still imports the historical ``handle_module_*`` functions from
this file.  The real implementations now live under ``docnexus_ai`` with
domain-oriented names.
"""

from docnexus_ai.document_operations import FormatAction, FormatPlan, handle_document_operation
from docnexus_ai.information_extraction import (
    chunk_text as _chunk_text,
    merge_chunk_extractions as _merge_chunk_extractions,
    handle_information_extraction,
)
from docnexus_ai.llm import get_chat_llm as _get_llm
from docnexus_ai.table_filling import handle_table_filling

from .schemas import *


def handle_module_1_format(input_data: Mod1_FormatInput) -> Mod1_FormatOutput:
    return handle_document_operation(input_data)


def handle_module_2_extract(input_data: Mod2_ExtractInput) -> Mod2_ExtractOutput:
    return handle_information_extraction(input_data)


def handle_module_3_fusion(input_data: Mod3_FusionInput, progress_callback=None) -> Mod3_FusionOutput:
    return handle_table_filling(input_data, progress_callback=progress_callback)


__all__ = [
    "FormatAction",
    "FormatPlan",
    "handle_document_operation",
    "handle_information_extraction",
    "handle_table_filling",
    "handle_module_1_format",
    "handle_module_2_extract",
    "handle_module_3_fusion",
    "_get_llm",
    "_chunk_text",
    "_merge_chunk_extractions",
]
