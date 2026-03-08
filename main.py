import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

# 在现有导入下面添加
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import ExtractionRecord, User, get_db, init_db
from services.auth import AuthService, get_current_user
from services.db_service import DBService
from services.llm_extractor import LLMExtractor
from services.parser import DocumentParser
from services.table_filler import TableFiller

app = FastAPI(title="文档理解系统", version="1.0.0")

# ==================== 启动事件 ====================


@app.on_event("startup")
def startup_event():
    init_db()
    print("🚀 服务启动完成")


# ==================== 数据模型 ====================


class ExtractRequest(BaseModel):
    fields: List[str]


class FillTableRequest(BaseModel):
    fields: List[str]


# ==================== 数据模型 ====================


class ExtractRequest(BaseModel):
    fields: List[str]


class FillTableRequest(BaseModel):
    fields: List[str]


# ===== 新增：认证相关模型 =====
class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: dict


# ==================== 基础接口 ====================


@app.get("/")
async def root():
    return {
        "message": "🚀 文档理解系统运行中",
        "version": "1.0.0",
        "docs": "/docs",
        "features": ["文档解析", "AI 提取", "自动填表", "历史记录"],
    }


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """仅上传并解析（不提取）"""
    try:
        result = await DocumentParser.parse_file(file)
        return {
            "status": "success",
            "data": {
                "filename": result["filename"],
                "file_type": result["file_type"],
                "char_count": result["char_count"],
                "preview": (
                    result["content"][:500] + "..."
                    if len(result["content"]) > 500
                    else result["content"]
                ),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"上传失败：{str(e)}")


# ==================== 核心提取接口 ====================


@app.post("/api/extract")
async def extract_info(
    file: UploadFile = File(..., description="源文档 (.docx, .txt 等)"),
    fields: str = Form(..., description="需要提取的字段，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """
    【核心接口】上传文档 + 提取字段 → 返回提取结果（存入数据库）
    """
    try:
        # 1. 解析文档
        parse_result = await DocumentParser.parse_file(file)
        text_content = parse_result["content"]

        # 2. 处理字段列表（支持中英文逗号）
        fields_list = [
            f.strip() for f in fields.replace("，", ",").split(",") if f.strip()
        ]

        if not fields_list:
            raise HTTPException(400, "请至少指定一个填写字段")

        # 3. 调用大模型提取数据
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        # 4. 保存记录到数据库（无论成功失败）
        status = "failed" if "error" in extracted_data else "success"
        record = DBService.save_extraction(
            db=db,
            filename=parse_result["filename"],
            file_type=parse_result["file_type"],
            fields_requested=fields_list,
            extracted_data=extracted_data,
            content_preview=text_content,
            status=status,
        )

        # 5. 检查是否提取失败
        if "error" in extracted_data:
            raise HTTPException(500, f"AI 提取失败：{extracted_data['error']}")

        return {
            "status": "success",
            "task_id": record.id,
            "filename": record.filename,
            "fields_requested": record.fields_requested,
            "extracted_data": record.extracted_data,
            "created_at": record.created_at.isoformat(),
            "query_url": f"/api/extractions/{record.id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"提取失败：{str(e)}")


# ==================== 表格填写接口 ====================


@app.post("/api/fill-table")
async def fill_table(
    template: UploadFile = File(..., description="Excel 模板文件 (.xlsx)"),
    document: UploadFile = File(..., description="源文档 (.docx, .txt 等)"),
    fields: str = Form(..., description="需要提取并填写的字段，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """
    【核心功能】上传 Excel 模板 + 文档 → 自动填写表格
    """
    try:
        # 1. 校验文件类型
        if not template.filename.lower().endswith(".xlsx"):
            raise HTTPException(400, "模板文件必须是 .xlsx 格式")

        # 2. 解析文档
        parse_result = await DocumentParser.parse_file(document)
        text_content = parse_result["content"]

        # 3. 处理字段列表
        fields_list = [
            f.strip() for f in fields.replace("，", ",").split(",") if f.strip()
        ]

        if not fields_list:
            raise HTTPException(400, "请至少指定一个填写字段")

        # 4. 调用大模型提取数据
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        if "error" in extracted_data:
            raise HTTPException(500, f"AI 提取失败：{extracted_data['error']}")

        # 5. 读取 Excel 模板
        template_bytes = await template.read()

        # 6. 填充表格
        filled_file = TableFiller.fill_template(
            template_bytes=template_bytes, extracted_data=extracted_data
        )

        # 7. 保存提取记录到数据库
        record = DBService.save_extraction(
            db=db,
            filename=parse_result["filename"],
            file_type=parse_result["file_type"],
            fields_requested=fields_list,
            extracted_data=extracted_data,
            content_preview=text_content,
            status="success",
        )

        # 8. 返回填充后的文件
        filename = f"filled_{template.filename}"
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
    except Exception as e:
        raise HTTPException(500, f"填表失败：{str(e)}")


@app.post("/api/fill-table/simple")
async def fill_table_simple(
    document: UploadFile = File(..., description="源文档"),
    fields: str = Form(..., description="需要提取的字段，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """
    【简化版】不上传模板，自动生成 Excel 并填写
    """
    try:
        # 1. 解析文档
        parse_result = await DocumentParser.parse_file(document)
        text_content = parse_result["content"]

        # 2. 处理字段（支持中英文逗号）
        # ✅ 关键修复：确保正确分割
        fields_list = [
            f.strip() for f in fields.replace("，", ",").split(",") if f.strip()
        ]

        print(f"📋 原始 fields: {fields}")
        print(f"📋 处理后的字段列表：{fields_list}")
        print(f"📋 字段列表类型：{type(fields_list)}")
        print(f"📋 字段数量：{len(fields_list)}")

        if not fields_list:
            raise HTTPException(400, "请至少指定一个填写字段")

        # 3. 提取数据
        extracted_data = LLMExtractor.extract_info(text_content, fields_list)

        if "error" in extracted_data:
            raise HTTPException(500, f"AI 提取失败：{extracted_data['error']}")

        print(f"📦 提取的数据：{extracted_data}")

        # 4. 自动生成模板并填充
        print(f"📊 创建模板，字段：{fields_list}")
        template_bytes = TableFiller.create_template_from_fields(fields_list)

        filled_file = TableFiller.fill_template(
            template_bytes=template_bytes.getvalue(), extracted_data=extracted_data
        )

        # 5. 保存提取记录到数据库
        record = DBService.save_extraction(
            db=db,
            filename=parse_result["filename"],
            file_type=parse_result["file_type"],
            fields_requested=fields_list,
            extracted_data=extracted_data,
            content_preview=text_content,
            status="success",
        )

        # 6. 返回文件
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
    except Exception as e:
        import traceback

        print(f"❌ 填表失败：\n{traceback.format_exc()}")
        raise HTTPException(500, f"填表失败：{str(e)}")


# ==================== 历史记录接口 ====================


@app.get("/api/extractions/search")
async def search_extractions(keyword: str, db: Session = Depends(get_db)):
    """搜索提取记录"""
    if not keyword or len(keyword) < 2:
        raise HTTPException(400, "关键词至少 2 个字符")

    records = DBService.search_extractions(db, keyword)

    return {
        "keyword": keyword,
        "total": len(records),
        "records": [
            {
                "id": r.id,
                "filename": r.filename,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "preview": r.content_preview[:200] + "..." if r.content_preview else "",
            }
            for r in records
        ],
    }


@app.get("/api/extractions")
async def list_extractions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 此接口只有登录后才能访问
):
    """获取提取历史记录列表"""
    records = DBService.list_extractions(db, limit=limit, offset=offset)

    return {
        "total": len(records),
        "limit": limit,
        "offset": offset,
        "records": [
            {
                "id": r.id,
                "filename": r.filename,
                "file_type": r.file_type,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@app.get("/api/extractions/{record_id}")
async def get_extraction_record(record_id: str, db: Session = Depends(get_db)):
    """查询提取记录（从数据库）"""
    record = DBService.get_extraction(db, record_id)

    if not record:
        raise HTTPException(404, "记录不存在")

    return {
        "id": record.id,
        "filename": record.filename,
        "file_type": record.file_type,
        "fields_requested": record.fields_requested,
        "extracted_data": record.extracted_data,
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@app.delete("/api/extractions/{record_id}")
async def delete_extraction_record(record_id: str, db: Session = Depends(get_db)):
    """删除提取记录"""
    success = DBService.delete_extraction(db, record_id)

    if not success:
        raise HTTPException(404, "记录不存在")

    return {"message": "删除成功", "record_id": record_id}


# ==================== 认证接口 ====================


@app.post("/api/auth/register", response_model=dict)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户是否存在
    existing = (
        db.query(User)
        .filter((User.username == user_data.username) | (User.email == user_data.email))
        .first()
    )

    if existing:
        raise HTTPException(400, "用户名或邮箱已存在")

    # 创建用户
    user = User(
        id=str(uuid.uuid4())[:8],
        username=user_data.username,
        email=user_data.email,
        hashed_password=AuthService.get_password_hash(user_data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "注册成功", "user_id": user.id, "username": user.username}


@app.post("/api/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """用户登录（仅支持邮箱）"""
    import re
    
    # 1. 获取并标准化邮箱
    email = form_data.username.strip().lower()
    
    # 2. 强制校验邮箱格式（❌ 不是邮箱直接拒绝）
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请使用邮箱地址登录"
        )
    
    # 3. 只通过邮箱查询用户（❌ 不再查询 username）
    user = db.query(User).filter(User.email == email).first()
    
    # 4. 验证密码
    if not user or not AuthService.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 5. 检查账户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 6. 创建 Token（使用 user.id 作为 sub）
    access_token = AuthService.create_access_token(
        data={"sub": user.id}, 
        expires_delta=timedelta(minutes=30)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {"id": user.id, "username": user.username, "email": user.email},
    }

@app.get("/api/auth/me", response_model=dict)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }