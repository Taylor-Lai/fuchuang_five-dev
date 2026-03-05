from typing import List

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
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
    file: UploadFile = File(...), request: ExtractRequest = Body(...)
):
    """
    【核心业务】上传文件 + 指定字段 -> 自动提取
    示例 fields: ["合同编号", "甲方", "乙方", "签署日期", "总金额"]
    """
    # 1. 解析文档
    parse_result = await DocumentParser.parse_file(file)
    text_content = parse_result["content"]

    if len(text_content) < 10:
        raise HTTPException(400, "文档内容过短，无法提取")

    # 2. 调用大模型提取
    # 这里会阻塞几秒，生产环境建议用 BackgroundTasks
    try:
        extracted_data = LLMExtractor.extract_info(text_content, request.fields)

        return {
            "status": "success",
            "filename": parse_result["filename"],
            "fields_requested": request.fields,
            "extracted_data": extracted_data,
            "confidence": "high",  # 实际可让模型返回置信度
        }
    except Exception as e:
        raise HTTPException(500, f"AI 提取失败: {str(e)}")
