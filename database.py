import os
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库文件路径（SQLite）
DATABASE_URL = "sqlite:///./doc_system.db"

# 创建引擎
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}  # SQLite 需要
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


# ==================== 数据模型 ====================


class ExtractionRecord(Base):
    """提取记录表"""

    __tablename__ = "extraction_records"

    id = Column(String, primary_key=True, index=True)  # UUID
    filename = Column(String, index=True)
    file_type = Column(String)
    fields_requested = Column(JSON)  # 请求的字段列表
    extracted_data = Column(JSON)  # 提取结果
    content_preview = Column(Text)  # 文档内容预览
    status = Column(String, default="success")  # success/failed
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class FileRecord(Base):
    """文件记录表"""

    __tablename__ = "file_records"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String)
    stored_path = Column(String)  # 文件存储路径
    file_size = Column(Integer)
    file_type = Column(String)
    parsed_content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


# ==================== 用户模型（新增） ====================


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    nickname = Column(String, nullable=True)  # 昵称
    gender = Column(String, nullable=True)  # 性别：男/女
    phone = Column(String, nullable=True)  # 手机号
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


# ==================== 依赖项 ====================


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 初始化 ====================


def init_db():
    """初始化数据库（创建表）"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库初始化成功")

    # 执行数据库迁移
    migrate_db()
    # 创建初始管理员账号
    create_initial_user()


def create_initial_user():
    """创建初始管理员账号"""
    from sqlalchemy.orm import Session

    from services.auth import AuthService

    db = SessionLocal()
    try:
        # 检查是否已有用户
        existing = db.query(User).first()
        if existing:
            print("ℹ️  已存在用户，跳过创建")
            return

        # 创建管理员
        admin = User(
            id="admin001",
            username="admin",
            email="admin@example.com",
            hashed_password=AuthService.get_password_hash("admin123"),
        )
        db.add(admin)
        db.commit()
        print("✅ 初始管理员创建成功 (用户名: admin, 密码: admin123)")
    finally:
        db.close() 

def migrate_db():
    """执行数据库迁移"""
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # 检查是否已存在这些字段
        result = db.execute(text("PRAGMA table_info(users)"))
        columns = [column[1] for column in result.fetchall()]
        
        # 如果字段不存在，添加它们
        if "nickname" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN nickname TEXT"))
            print("✅ 添加 nickname 字段成功")
        
        if "gender" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN gender TEXT"))
            print("✅ 添加 gender 字段成功")
        
        if "phone" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN phone TEXT"))
            print("✅ 添加 phone 字段成功")
        
        db.commit()
        print("✅ 数据库迁移完成")
    except Exception as e:
        print(f"❌ 迁移失败：{str(e)}")
        db.rollback()
    finally:
        db.close()