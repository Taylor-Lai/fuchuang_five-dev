import os
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
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


# dd7064b2
