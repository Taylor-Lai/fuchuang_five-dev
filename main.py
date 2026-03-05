from typing import List

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.llm_extractor import LLMExtractor
from services.parser import DocumentParser

app = FastAPI(title="文档理解系统", version="0.2.0")


# 定义请求模型
class ExtractRequest(BaseModel):
    fields: List[str]  # 例如: ["甲方", "金额", "日期"]


@app.get("/")
async def root():
    return {"message": "🚀 服务运行中", "provider": "Ready"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """仅上传并解析"""
    result = await DocumentParser.parse_file(file)
    return {"status": "success", "data": result}


@app.post("/api/extract")
async def extract_info(
    file: UploadFile = File(..., description="上传的文档 (.docx, .txt等)"),
    fields: str = Form(
        ..., description="需要提取的字段，用逗号分隔。例如：甲方,乙方,金额"
    ),
):
    """
    【优化版】上传文件 + 提取字段
    现在只需要在 Swagger 里填 "字段1,字段2" 即可，不用写 JSON
    """
    # 1. 解析文档
    try:
        parse_result = await DocumentParser.parse_file(file)
        text_content = parse_result["content"]
    except Exception as e:
        raise HTTPException(400, f"文档解析失败: {str(e)}")

    if len(text_content) < 10:
        raise HTTPException(400, "文档内容过短，无法提取")

    # 2. 处理字段输入 (将 "学生姓名,指导教师" 转为列表)
    fields_list = [f.strip() for f in fields.split(",") if f.strip()]

    if not fields_list:
        raise HTTPException(400, "请至少指定一个提取字段")

    # 3. 调用大模型提取
    try:
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        return {
            "status": "success",
            "filename": parse_result["filename"],
            "fields_requested": fields_list,
            "extracted_data": extracted_data,
        }
    except Exception as e:
        raise HTTPException(500, f"AI 提取失败: {str(e)}")
