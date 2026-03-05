import os
import uuid
from typing import List, Optional
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.llm_extractor import LLMExtractor
from services.parser import DocumentParser
from services.table_filler import TableFiller

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


# 新增：填表请求模型
class FillTableRequest(BaseModel):
    fields: List[str]  # 需要提取的字段


# 临时存储提取结果（实际项目应该用数据库）
extracted_data_store = {}


@app.post("/api/fill-table")
async def fill_table(
    template: UploadFile = File(..., description="Excel 模板文件 (.xlsx)"),
    document: UploadFile = File(..., description="源文档 (.docx, .txt 等)"),
    fields: str = Form(..., description="需要提取并填写的字段，用逗号分隔"),
):
    """
    【核心功能】上传 Excel 模板 + 文档 → 自动填写表格
    """
    # 1. 校验文件类型
    if not template.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "模板文件必须是 .xlsx 格式")

    # 2. 解析文档
    try:
        parse_result = await DocumentParser.parse_file(document)
        text_content = parse_result["content"]
    except HTTPException:
        raise
    except Exception as e:  # ← 修改这里
        raise HTTPException(400, f"文档解析失败：{str(e)}")

    # 3. 处理字段列表
    fields_list = [f.strip() for f in fields.replace("，", ",").split(",") if f.strip()]
    print(f"📋 处理后的字段列表：{fields_list}")  # 调试打印
    if not fields_list:
        raise HTTPException(400, "请至少指定一个填写字段")

    # 4. 调用大模型提取数据
    try:
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        if "error" in extracted_data:
            raise HTTPException(500, f"AI 提取失败：{extracted_data['error']}")

    except HTTPException:
        raise
    except Exception as e:  # ← 修改这里
        raise HTTPException(500, f"AI 提取失败：{str(e)}")

    # 5. 读取 Excel 模板
    try:
        template_bytes = await template.read()
    except Exception as e:  # ← 修改这里
        raise HTTPException(500, f"读取模板失败：{str(e)}")

    # 6. 填充表格
    try:
        filled_file = TableFiller.fill_template(
            template_bytes=template_bytes, extracted_data=extracted_data
        )
    except Exception as e:  # ← 修改这里
        raise HTTPException(500, f"表格填充失败：{str(e)}")

    # 7. 返回填充后的文件
    filename = f"filled_{template.filename}"

    encoded_filename = quote(filename)

    return StreamingResponse(
        filled_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@app.post("/api/fill-table/simple")
async def fill_table_simple(
    document: UploadFile = File(..., description="源文档"),
    fields: str = Form(..., description="需要提取的字段"),
):
    """
    【简化版】不上传模板，自动生成 Excel 并填写
    """
    try:
        # 1. 解析文档
        parse_result = await DocumentParser.parse_file(document)
        text_content = parse_result["content"]

        # 2. 处理字段
        # 先把中文逗号替换为英文逗号，再分割
        fields_list = [
            f.strip() for f in fields.replace("，", ",").split(",") if f.strip()
        ]
        print(f"📋 处理后的字段列表：{fields_list}")  # 调试打印

        # 3. 提取数据
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        if "error" in extracted_data:
            raise HTTPException(500, f"AI 提取失败：{extracted_data['error']}")

        # 4. 自动生成模板并填充
        template_bytes = TableFiller.create_template_from_fields(fields_list)

        filled_file = TableFiller.fill_template(
            template_bytes=template_bytes.getvalue(), extracted_data=extracted_data
        )

        # 5. 返回文件
        filename = f"auto_filled_{document.filename.split('.')[0]}.xlsx"

        encoded_filename = quote(filename)

        return StreamingResponse(
            filled_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            },
        )

    except HTTPException:
        raise
    except Exception as e:  # ← 修改这里
        raise HTTPException(500, f"填表失败：{str(e)}")


@app.get("/api/extract-and-store/{task_id}")
async def get_stored_extraction(task_id: str):
    """查询已存储的提取结果"""
    if task_id not in extracted_data_store:
        raise HTTPException(404, "任务不存在")
    return extracted_data_store[task_id]
