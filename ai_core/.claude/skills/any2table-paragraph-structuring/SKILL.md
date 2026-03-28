---
name: any2table-paragraph-structuring
description: Extract structured candidate rows from source document paragraphs using the target template schema.
version: 0.1.0
tags:
  - any2table
  - extraction
  - paragraph-structuring
  - docx
inputs:
  - user_request_doc
  - task_spec
  - template_fields
  - source_document
  - paragraphs
outputs:
  - records
  - reasoning_summary
---

# Purpose
Convert narrative paragraphs into structured candidate rows that can be merged into the fill pipeline.

# When To Use
- Source documents contain useful paragraph descriptions instead of clean tables.
- The rule extractor can read the document, but cannot directly map the paragraph content into template fields.
- We want a conservative LLM extraction path that improves coverage without replacing the deterministic path.

# Required Output
Return one JSON object with:
- `records`: array of candidate records
- `reasoning_summary`: short explanation

Each item in `records` must contain:
- `values`: object whose keys use the exact template field names
- `source_paragraph_ids`: array of paragraph ids used for this record
- `confidence`: number between 0 and 1
- `notes`: array of short notes

# Procedure
1. Read the target template fields and only output those exact field names.
2. Extract values only when they are directly supported by the source paragraphs.
3. If a paragraph is province-level but clearly belongs to China and the target schema does not contain a province field, you may set `国家/地区` to `China` and put the province name in `notes`.
4. Keep unsupported fields as `null`.
5. Prefer complete records, but partial records are allowed when they add useful supported information.
6. Do not aggregate multiple paragraphs into a numeric sum unless the sum is explicitly stated.

# Guardrails
- Do not invent values that are not directly supported by the input paragraphs.
- Do not output fields outside the template schema.
- If the metric semantics do not match exactly, leave the field as `null` and explain the mismatch in `notes`.
- Use English names such as `China` and `Asia` when the target field is a country or continent and the paragraph clearly refers to those entities.
- Return strict JSON only.