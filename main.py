import os
import uuid
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import ExtractionRecord, User, get_db, init_db
from services.auth import AuthService, get_current_user
from services.db_service import DBService
from services.llm_extractor import LLMExtractor
from services.parser import DocumentParser
from services.table_filler import TableFiller

# 导入 ai_core engine 模块
from ai_core.engine.engine import handle_module_1_format, handle_module_2_extract, handle_module_3_fusion
from ai_core.engine.schemas import Mod1_FormatInput, Mod2_ExtractInput, Mod3_FusionInput

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


# ===== 新增：认证相关模型 =====
class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: dict


# ===== 新增：修改个人资料模型 =====
class UserProfileUpdate(BaseModel):
    """修改个人资料请求模型"""
    nickname: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


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


# ==================== 核心提取接口（已删除，使用新的 /doc-extract/upload）====================


# ==================== 表格填写接口（已删除，使用新的 /table-fill/upload）====================


@app.post("/table-fill/simple")
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


@app.get("/doc-extract/search")
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


@app.get("/doc-extract")
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


@app.get("/doc-extract/{record_id}")
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


@app.delete("/doc-extract/{record_id}")
async def delete_extraction_record(record_id: str, db: Session = Depends(get_db)):
    """删除提取记录"""
    success = DBService.delete_extraction(db, record_id)

    if not success:
        raise HTTPException(404, "记录不存在")

    return {"message": "删除成功", "record_id": record_id}


# ==================== 认证接口 ====================


@app.post("/auth/register", response_model=dict)
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


@app.post("/auth/login", response_model=Token)
async def login(
    login_data: LoginRequest, 
    db: Session = Depends(get_db),
    request: Request = None
):
    """用户登录"""
    # 根据邮箱查找用户
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not AuthService.verify_password(
        login_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 更新登录信息
    from datetime import datetime
    user.last_login_time = datetime.now()
    user.last_activity_time = datetime.now()  # 初始化最后活动时间
    if request:
        user.last_login_ip = request.client.host
    user.login_status = "在线"
    db.commit()
    db.refresh(user)

    # 创建 Token (使用用户ID作为sub，过期时间为3小时)
    access_token = AuthService.create_access_token(
        data={"sub": user.id}, expires_delta=timedelta(hours=3)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {"id": user.id, "username": user.username, "email": user.email},
    }


@app.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """用户登出"""
    # 更新登录状态为离线
    current_user.login_status = "离线"
    db.commit()
    db.refresh(current_user)
    
    return {
        "code": 200,
        "message": "登出成功",
        "data": {}
    }


@app.post("/auth/heartbeat")
async def heartbeat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    用户心跳接口，用于保持在线状态
    前端需要定期调用（建议每5分钟一次）
    """
    # 更新最后活动时间（不更新 last_login_time）
    current_user.last_activity_time = datetime.now()
    # 确保状态为在线
    if current_user.login_status != "在线":
        current_user.login_status = "在线"
    db.commit()
    db.refresh(current_user)
    
    return {
        "code": 200,
        "message": "心跳成功",
        "data": {
            "user_id": current_user.id,
            "login_status": current_user.login_status
        }
    }


@app.get("/user/profile", response_model=dict)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """获取个人信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "gender": current_user.gender,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
    }


# 添加修改个人资料接口
@app.put("/user/profile", response_model=dict)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改个人资料"""
    # 检查邮箱是否已被其他用户使用
    if profile_data.email and profile_data.email != current_user.email:
        existing_user = db.query(User).filter(User.email == profile_data.email).first()
        if existing_user:
            raise HTTPException(400, "邮箱已被其他用户使用")
    
    # 验证性别字段
    if profile_data.gender and profile_data.gender not in ["男", "女"]:
        raise HTTPException(400, "性别只能是'男'或'女'")
    
    # 验证手机号格式（简单验证）
    if profile_data.phone:
        import re
        phone_regex = r'^1[3-9]\d{9}$'
        if not re.match(phone_regex, profile_data.phone):
            raise HTTPException(400, "手机号格式不正确")
    
    # 更新用户信息
    if profile_data.nickname is not None:
        current_user.nickname = profile_data.nickname
    if profile_data.gender is not None:
        current_user.gender = profile_data.gender
    if profile_data.email is not None:
        current_user.email = profile_data.email
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "个人资料更新成功",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "nickname": current_user.nickname,
            "gender": current_user.gender,
            "phone": current_user.phone,
        }
    }



# ==================== 文档智能操作接口（已删除，使用新的 /doc-chat/upload）====================

# ==================== 新接口：基于 ai_core 的三个模块 ====================

@app.post("/doc-chat/upload")
async def doc_chat_upload(
    background_tasks: BackgroundTasks,
    command: str = Form(..., description="自然语言指令，例如：'把第一段变成红色字体，并且加粗'"),
    document: UploadFile = File(..., description="Word 文档文件 (.docx)"),
):
    """
    【模块一】文档智能操作交互
    
    通过自然语言指令对文档进行编辑、排版、格式调整等操作
    """
    try:
        # 0. 校验文件类型
        if not document.filename.lower().endswith(".docx"):
            raise HTTPException(400, "仅支持 .docx 文件进行格式调整")

        # 1. 保存上传的文件到临时目录
        temp_dir = Path(tempfile.gettempdir()) / f"doc_chat_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = temp_dir / document.filename
        with open(file_path, "wb") as f:
            content = await document.read()
            f.write(content)
        
        # 2. 调用 ai_core engine 的模块一处理函数
        input_data = Mod1_FormatInput(
            file_path=str(file_path),
            natural_language_cmd=command
        )
        
        result = handle_module_1_format(input_data)
        
        # 3. 返回处理后的文件，并设置后台任务删除临时目录
        if result.status == "success":
            def cleanup_temp():
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                    print(f"🧹 已清理临时目录: {temp_dir}")
                except Exception as e:
                    print(f"⚠️ 清理失败: {e}")

            background_tasks.add_task(cleanup_temp)

            # 处理中文文件名编码
            filename = f"formatted_{document.filename}"
            encoded_filename = quote(filename)

            return FileResponse(
                result.processed_file_path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        else:
            raise HTTPException(500, f"文档操作失败：{result.message}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"文档操作失败：{str(e)}")


# 模块二：非结构化文档信息提取
@app.post("/doc-extract/upload")
async def doc_extract_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="源文档 (.docx, .txt, .md, .xlsx 等)"),
    fields: str = Form(..., description="需要提取的字段，用逗号分隔"),
    db: Session = Depends(get_db),
):
    """
    【模块二】非结构化文档信息提取
    
    从文档中提取指定的字段信息
    """
    try:
        # 1. 保存上传的文件到临时目录
        temp_dir = Path(tempfile.gettempdir()) / f"doc_extract_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = temp_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 2. 处理字段列表（支持中英文逗号）
        fields_list = [
            f.strip() for f in fields.replace("，", ",").split(",") if f.strip()
        ]
        
        if not fields_list:
            raise HTTPException(400, "请至少指定一个提取字段")
        
        # 3. 调用 ai_core engine 的模块二处理函数
        input_data = Mod2_ExtractInput(
            file_path=str(file_path),
            target_entities=fields_list
        )
        
        result = handle_module_2_extract(input_data)

        # 4. 后台任务删除临时目录
        def cleanup_temp():
            import shutil
            try:
                shutil.rmtree(temp_dir)
                print(f"🧹 已清理临时目录: {temp_dir}")
            except Exception as e:
                print(f"⚠️ 清理失败: {e}")

        background_tasks.add_task(cleanup_temp)
        
        # 5. 保存记录到数据库
        if result.status == "success":
            record = DBService.save_extraction(
                db=db,
                filename=file.filename,
                file_type=file.filename.split('.')[-1] if '.' in file.filename else 'unknown',
                fields_requested=fields_list,
                extracted_data=result.extracted_data,
                content_preview=str(result.extracted_data)[:500],
                status="success",
            )
            
            return {
                "status": "success",
                "task_id": record.id,
                "filename": file.filename,
                "fields_requested": fields_list,
                "extracted_data": result.extracted_data,
                "created_at": record.created_at.isoformat(),
            }
        else:
            raise HTTPException(500, f"信息提取失败：{result.message}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"信息提取失败：{str(e)}")


# 模块三：表格自定义数据填写
@app.post("/table-fill/upload")
async def table_fill_upload(
    background_tasks: BackgroundTasks,
    template: UploadFile = File(..., description="Excel 模板文件 (.xlsx)"),
    documents: List[UploadFile] = File(..., description="源文档 (.docx, .txt, .md 等)"),
    user_request: str = Form("", description="用户的附加自然语言要求（可选）"),
    db: Session = Depends(get_db),
):
    """
    【模块三】表格自定义数据填写（多源融合填表）
    
    上传 Excel 模板和源文档，自动提取信息并填写到表格中
    使用多智能体系统进行跨文档特征提取与对齐
    """
    try:
        # 1. 校验模板文件类型
        if not template.filename.lower().endswith(".xlsx"):
            raise HTTPException(400, "模板文件必须是 .xlsx 格式")
        
        # 2. 创建工作空间目录
        workspace_dir = Path(tempfile.gettempdir()) / f"table_fill_{uuid.uuid4().hex[:8]}"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 保存模板文件
        template_path = workspace_dir / f"模板{template.filename}"
        with open(template_path, "wb") as f:
            content = await template.read()
            f.write(content)
        
        # 4. 保存源文档
        source_files = []
        for document in documents:
            doc_path = workspace_dir / document.filename
            with open(doc_path, "wb") as f:
                content = await document.read()
                f.write(content)
            source_files.append(doc_path)
        
        # 5. 调用 ai_core engine 的模块三处理函数
        task_id = str(uuid.uuid4())[:8]
        input_data = Mod3_FusionInput(
            task_id=task_id,
            workspace_dir=str(workspace_dir),
            user_request=user_request if user_request else None
        )
        
        result = handle_module_3_fusion(input_data)
        
        # 6. 返回填充后的文件，并设置后台任务删除临时目录
        if result.status == "success":
            # 保存记录到数据库
            # 构建文件名列表
            doc_filenames = [doc.filename for doc in documents]
            filename_str = f"{template.filename} + {', '.join(doc_filenames)}"
            
            record = DBService.save_extraction(
                db=db,
                filename=filename_str,
                file_type="xlsx",
                fields_requested=[],
                extracted_data={"output_path": result.output_excel_path},
                content_preview=f"多源数据融合，生成文件：{result.output_excel_path}",
                status="success",
            )
            
            def cleanup_temp():
                import shutil
                try:
                    shutil.rmtree(workspace_dir)
                    print(f"🧹 已清理临时目录: {workspace_dir}")
                except Exception as e:
                    print(f"⚠️ 清理失败: {e}")

            background_tasks.add_task(cleanup_temp)

            # 处理中文文件名编码
            filename = f"filled_{template.filename}"
            encoded_filename = quote(filename)
            print(f"✅ 生成的输出文件路径: {result.output_excel_path}")
            return FileResponse(
                result.output_excel_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        else:
            raise HTTPException(500, f"表格填写失败：{result.error_msg}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"表格填写失败：{str(e)}")


# ==================== 后台管理接口 ====================

# 新增：用户列表分页接口
@app.get("/admin/user/page")
async def get_user_page(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】用户列表分页接口
    
    - page: 页码，默认1
    - page_size: 每页数量，默认10
    - keyword: 搜索关键词（用户名/邮箱）
    - status: 状态筛选（active/inactive）
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 清理长时间未活动的在线用户（超过15分钟没有心跳）
    timeout = datetime.now() - timedelta(minutes=15)
    inactive_users = db.query(User).filter(
        User.login_status == "在线",
        User.last_activity_time < timeout
    ).all()
    
    for user in inactive_users:
        user.login_status = "离线"
    
    if inactive_users:
        db.commit()
    
    # 构建查询
    query = db.query(User)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            (User.username.ilike(f"%{keyword}%") | 
             User.email.ilike(f"%{keyword}%") |
             User.nickname.ilike(f"%{keyword}%")
            )
        )
    
    # 状态筛选
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "inactive":
        query = query.filter(User.is_active == False)
    
    # 计算总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()
    
    # 构建响应
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "gender": user.gender,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "login_status": user.login_status,
            "last_login_time": user.last_login_time.isoformat() if user.last_login_time else None,
            "last_activity_time": user.last_activity_time.isoformat() if user.last_activity_time else None,
            "last_login_ip": user.last_login_ip,
            "created_at": user.created_at.isoformat()
        })
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "list": user_list
        }
    }


# 新增：用户详情接口
@app.get("/admin/user/{user_id}")
async def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】用户详情接口
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 构建响应
    user_info = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "gender": user.gender,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
        "login_status": user.login_status,
        "last_login_time": user.last_login_time.isoformat() if user.last_login_time else None,
        "last_activity_time": user.last_activity_time.isoformat() if user.last_activity_time else None,
        "last_login_ip": user.last_login_ip,
        "remark": user.remark,
        "created_at": user.created_at.isoformat()
    }
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": user_info
    }


# 新增：启用/禁用用户接口
@app.put("/admin/user/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】启用/禁用用户接口
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不允许禁用自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")
    
    # 更新状态
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": {
            "user_id": user.id,
            "is_active": user.is_active
        }
    }


# 新增：设置管理员权限接口
@app.put("/admin/user/{user_id}/role")
async def update_user_role(
    user_id: str,
    is_admin: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】设置或取消用户管理员权限接口
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不允许修改自己的权限
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的管理员权限")
    
    # 更新角色
    user.role = "管理员" if is_admin else "普通用户"
    db.commit()
    db.refresh(user)
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": {
            "user_id": user.id,
            "role": user.role
        }
    }


# 新增：删除用户接口
@app.delete("/admin/user/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】删除用户接口
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不允许删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    
    # 删除用户
    db.delete(user)
    db.commit()
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": {
            "user_id": user_id
        }
    }


# 新增：获取后台统计数据接口
@app.get("/admin/statistics")
async def get_admin_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    【管理员】获取后台统计数据接口
    会自动清理超过15分钟没有心跳的在线用户
    """
    # 检查管理员权限
    if current_user.role != "管理员":
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 清理长时间未活动的在线用户（超过15分钟没有心跳）
    timeout = datetime.now() - timedelta(minutes=15)
    inactive_users = db.query(User).filter(
        User.login_status == "在线",
        User.last_activity_time < timeout
    ).all()
    
    for user in inactive_users:
        user.login_status = "离线"
    
    if inactive_users:
        db.commit()
        print(f"🧹 自动清理 {len(inactive_users)} 个超时未活动的用户")
    
    # 统计总用户数
    total_users = db.query(User).count()
    
    # 统计在线用户数（15分钟内有活动的用户）
    online_users = db.query(User).filter(
        User.login_status == "在线",
        User.last_activity_time >= timeout
    ).count()
    
    # 统计正常用户数（活跃状态）
    normal_users = db.query(User).filter(User.is_active == True).count()
    
    # 构建响应
    statistics = {
        "total_users": total_users,
        "online_users": online_users,
        "normal_users": normal_users
    }
    
    return {
        "code": 200,
        "message": "操作成功",
        "data": statistics
    }
