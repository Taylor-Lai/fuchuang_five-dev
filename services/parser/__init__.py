from pathlib import Path
from typing import List
from .md_parser import MarkdownParser
from .txt_parser import TxtParser
from .docx_parser import DocxParser
from .xlsx_parser import XlsxParser
from .base import DocumentChunk

def parse_folder(folder_path: str) -> List[DocumentChunk]:
    folder = Path(folder_path)
    all_chunks: List[DocumentChunk] = []

    md_parser   = MarkdownParser()
    txt_parser  = TxtParser()
    docx_parser = DocxParser()
    xlsx_parser = XlsxParser()

    for file in folder.rglob("*"):
        if file.suffix == ".md":
            all_chunks.extend(md_parser.parse(str(file)))
        elif file.suffix == ".txt":
            all_chunks.extend(txt_parser.parse(str(file)))
        elif file.suffix == ".docx":
            all_chunks.extend(docx_parser.parse(str(file)))
        elif file.suffix == ".xlsx":
            all_chunks.extend(xlsx_parser.parse(str(file)))

    # 全局连续编号
    for i, chunk in enumerate(all_chunks):
        chunk.metadata["chunk_index"] = i

    print(f"[解析完成] 共生成 {len(all_chunks)} 个 chunks")
    return all_chunks