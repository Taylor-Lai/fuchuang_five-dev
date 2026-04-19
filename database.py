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
    accountStatus = Column(String, default="正常")  # 账户状态：正常/异常
    created_at = Column(DateTime, default=datetime.now)
    # 新增字段
    role = Column(String, default="普通用户")  # 用户角色：管理员、普通用户
    last_login_time = Column(DateTime, nullable=True)  # 最后登录时间
    last_login_ip = Column(String, nullable=True)  # 最后登录IP
    login_status = Column(String, default="离线")  # 登录状态：在线、离线
    last_activity_time = Column(DateTime, nullable=True)  # 最后活动时间（用于心跳检测）
    remark = Column(Text, nullable=True)  # 备注


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
        
        # 处理 accountStatus 字段
        if "accountStatus" in columns:
            # 检查是否需要从布尔值转换为字符串
            # 获取字段类型
            result = db.execute(text("PRAGMA table_info(users)"))
            field_info = result.fetchall()
            accountStatus_type = None
            for field in field_info:
                if field[1] == "accountStatus":
                    accountStatus_type = field[2]
                    break
            
            if accountStatus_type and "BOOLEAN" in accountStatus_type:
                print("ℹ️  开始将 accountStatus 字段从布尔值转换为字符串...")
                try:
                    # 1. 创建临时表
                    db.execute(text("""
                        CREATE TABLE users_temp (
                            id VARCHAR NOT NULL,
                            username VARCHAR NOT NULL,
                            email VARCHAR,
                            hashed_password VARCHAR NOT NULL,
                            nickname TEXT,
                            gender TEXT,
                            phone TEXT,
                            accountStatus TEXT DEFAULT '正常',
                            created_at DATETIME,
                            role TEXT DEFAULT '普通用户',
                            last_login_time DATETIME,
                            last_login_ip TEXT,
                            login_status TEXT DEFAULT '离线',
                            last_activity_time DATETIME,
                            remark TEXT,
                            PRIMARY KEY (id)
                        )
                    """))
                    
                    # 2. 复制数据，将布尔值转换为字符串
                    db.execute(text("""
                        INSERT INTO users_temp 
                        SELECT id, username, email, hashed_password, nickname, gender, phone, 
                               CASE WHEN accountStatus = 1 THEN '正常' ELSE '异常' END, 
                               created_at, role, last_login_time, last_login_ip, 
                               login_status, last_activity_time, remark
                        FROM users
                    """))
                    
                    # 3. 删除旧表
                    db.execute(text("DROP TABLE users"))
                    
                    # 4. 重命名临时表
                    db.execute(text("ALTER TABLE users_temp RENAME TO users"))
                    
                    # 5. 重建索引
                    db.execute(text("CREATE INDEX ix_users_id ON users (id)"))
                    db.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
                    db.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
                    
                    print("✅ 成功将 accountStatus 字段从布尔值转换为字符串")
                    
                    # 更新 columns 列表
                    result = db.execute(text("PRAGMA table_info(users)"))
                    columns = [column[1] for column in result.fetchall()]
                except Exception as e:
                    print(f"❌ 转换 accountStatus 字段失败：{str(e)}")
                    db.rollback()
                    raise
        elif "is_active" in columns:
            # 重命名 is_active 列为 accountStatus（SQLite 不支持直接重命名，需要重建表）
            print("ℹ️  开始迁移 is_active 列为 accountStatus...")
            try:
                # 1. 创建临时表
                db.execute(text("""
                    CREATE TABLE users_temp (
                        id VARCHAR NOT NULL,
                        username VARCHAR NOT NULL,
                        email VARCHAR,
                        hashed_password VARCHAR NOT NULL,
                        nickname TEXT,
                        gender TEXT,
                        phone TEXT,
                        accountStatus TEXT DEFAULT '正常',
                        created_at DATETIME,
                        role TEXT DEFAULT '普通用户',
                        last_login_time DATETIME,
                        last_login_ip TEXT,
                        login_status TEXT DEFAULT '离线',
                        last_activity_time DATETIME,
                        remark TEXT,
                        PRIMARY KEY (id)
                    )
                """))
                
                # 2. 复制数据，将布尔值转换为字符串
                db.execute(text("""
                    INSERT INTO users_temp 
                    SELECT id, username, email, hashed_password, nickname, gender, phone, 
                           CASE WHEN is_active = 1 THEN '正常' ELSE '异常' END, 
                           created_at, role, last_login_time, last_login_ip, 
                           login_status, last_activity_time, remark
                    FROM users
                """))
                
                # 3. 删除旧表
                db.execute(text("DROP TABLE users"))
                
                # 4. 重命名临时表
                db.execute(text("ALTER TABLE users_temp RENAME TO users"))
                
                # 5. 重建索引
                db.execute(text("CREATE INDEX ix_users_id ON users (id)"))
                db.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
                db.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
                
                print("✅ 成功将 is_active 列重命名为 accountStatus")
                
                # 更新 columns 列表
                result = db.execute(text("PRAGMA table_info(users)"))
                columns = [column[1] for column in result.fetchall()]
            except Exception as e:
                print(f"❌ 迁移 is_active 列失败：{str(e)}")
                db.rollback()
                raise
        
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
        
        # 新增字段
        if "role" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN role TEXT DEFAULT '普通用户'"))
            print("✅ 添加 role 字段成功")
        
        if "last_login_time" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN last_login_time DATETIME"))
            print("✅ 添加 last_login_time 字段成功")
        
        if "last_login_ip" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN last_login_ip TEXT"))
            print("✅ 添加 last_login_ip 字段成功")
        
        if "login_status" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN login_status TEXT DEFAULT '离线'"))
            print("✅ 添加 login_status 字段成功")
        
        if "remark" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN remark TEXT"))
            print("✅ 添加 remark 字段成功")
        
        if "last_activity_time" not in columns:
            db.execute(text("ALTER TABLE users ADD COLUMN last_activity_time DATETIME"))
            print("✅ 添加 last_activity_time 字段成功")
        
        # 将指定邮箱的用户设置为管理员
        admin_emails = ["admin@example.com", "1234567890@qq.com"]
        for email in admin_emails:
            result = db.execute(
                text("UPDATE users SET role = '管理员' WHERE email = :email"),
                {"email": email}
            )
            if result.rowcount > 0:
                print(f"✅ 将 {email} 设置为管理员")
            else:
                print(f"⚠️ 未找到邮箱为 {email} 的用户")
        
        db.commit()
        print("✅ 数据库迁移完成")
    except Exception as e:
        print(f"❌ 迁移失败：{str(e)}")
        db.rollback()
    finally:
        db.close()