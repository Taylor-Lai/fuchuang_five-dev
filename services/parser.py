import os
from io import BytesIO
from typing import Optional

import docx
import pandas as pd
from fastapi import HTTPException, UploadFile


class DocumentParser:
    """文档解析器：支持 docx, xlsx, txt, md"""

    @staticmethod
    async def parse_file(file: UploadFile) -> dict:
        """
        主入口：根据文件后缀自动选择解析策略
        返回：{"filename": "...", "content": "...", "meta": {...}}
        """
        filename = file.filename
        if not filename:
            raise HTTPException(400, "文件名不能为空")

        # 获取后缀名 (转为小写)
        suffix = os.path.splitext(filename)[1].lower()

        # 读取文件内容到内存
        content_bytes = await file.read()

        try:
            if suffix == ".docx":
                text = DocumentParser._parse_docx(content_bytes)
            elif suffix == ".xlsx":
                text = DocumentParser._parse_xlsx(content_bytes)
            elif suffix in [".txt", ".md"]:
                text = DocumentParser._parse_text(content_bytes)
            else:
                raise HTTPException(400, f"不支持的文件类型: {suffix}")

            return {
                "filename": filename,
                "content": text,
                "char_count": len(text),
                "file_type": suffix,
            }
        except Exception as e:
            raise HTTPException(500, f"文件解析失败: {str(e)}")

    @staticmethod
    def _parse_docx(content_bytes: bytes) -> str:
        """解析 Word 文档"""
        try:
            # 检查文件是否为有效的 ZIP 文件
            import zipfile
            zipfile.ZipFile(BytesIO(content_bytes))
        except zipfile.BadZipFile:
            raise Exception("上传的文件不是有效的 .docx 文件")
    
        try:
            doc = docx.Document(BytesIO(content_bytes))
            # 提取所有段落文本，用换行符连接
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            # 详细的错误信息
            import traceback
            print(f"解析 .docx 文件失败: {str(e)}")
            print(traceback.format_exc())
            raise Exception(f"Word 文档解析失败: {str(e)}")

    @staticmethod
    def _parse_xlsx(content_bytes: bytes) -> str:
        """解析 Excel 表格 (转为 Markdown 格式，方便 LLM 理解)"""
        df = pd.read_excel(BytesIO(content_bytes))
        # 转为 Markdown 表格字符串
        return df.to_markdown(index=False)

    @staticmethod
    def _parse_text(content_bytes: bytes) -> str:
        """解析纯文本"""
        # 尝试 utf-8 解码，失败则尝试 gbk (兼容中文 Windows)
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return content_bytes.decode("gbk")