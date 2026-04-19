import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import String  # ← 添加这行
from sqlalchemy.orm import Session

from database import ExtractionRecord, FileRecord


class DBService:
    """数据库服务层"""

    @staticmethod
    def save_extraction(
        db: Session,
        filename: str,
        file_type: str,
        fields_requested: List[str],
        extracted_data: Dict,  # 修复了变量名拼写错误 extracted_ Dict -> extracted_data
        content_preview: str = "",
        status: str = "success",
    ) -> ExtractionRecord:
        """保存提取记录"""
        record_id = str(uuid.uuid4())[:8]

        record = ExtractionRecord(
            id=record_id,
            filename=filename,
            file_type=file_type,
            fields_requested=fields_requested,
            extracted_data=extracted_data,
            content_preview=content_preview[:1000] if content_preview else "",
            status=status,
            created_at=datetime.now(),  # 补充创建时间（如果模型需要）
        )

        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            print(f"💾 保存提取记录：{record_id}")
            return record
        except Exception as e:
            db.rollback()  # 出错时回滚事务
            print(f"❌ 保存提取记录失败：{e}")
            raise e  # 抛出异常让上层处理

    @staticmethod
    def get_extraction(db: Session, record_id: str) -> Optional[ExtractionRecord]:
        """查询提取记录"""
        return (
            db.query(ExtractionRecord).filter(ExtractionRecord.id == record_id).first()
        )

    @staticmethod
    def list_extractions(
        db: Session, limit: int = 20, offset: int = 0
    ) -> List[ExtractionRecord]:
        """获取提取记录列表"""
        return (
            db.query(ExtractionRecord)
            .order_by(ExtractionRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete_extraction(db: Session, record_id: str) -> bool:
        """删除提取记录"""
        try:
            record = (
                db.query(ExtractionRecord)
                .filter(ExtractionRecord.id == record_id)
                .first()
            )
            if record:
                db.delete(record)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"❌ 删除提取记录失败：{e}")
            raise e

    @staticmethod
    def save_file(
        db: Session,
        original_filename: str,
        stored_path: str,
        file_size: int,
        file_type: str,
        parsed_content: str = "",
    ) -> FileRecord:
        """保存文件记录"""
        record_id = str(uuid.uuid4())[:8]

        record = FileRecord(
            id=record_id,
            original_filename=original_filename,
            stored_path=stored_path,
            file_size=file_size,
            file_type=file_type,
            parsed_content=parsed_content[:5000] if parsed_content else "",
            created_at=datetime.now(),  # 补充创建时间
        )

        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            print(f"💾 保存文件记录：{record_id}")
            return record
        except Exception as e:
            db.rollback()
            print(f"❌ 保存文件记录失败：{e}")
            raise e

    @staticmethod
    def search_extractions(db: Session, keyword: str) -> List[ExtractionRecord]:
        """搜索提取记录（支持多字段搜索）"""
        from sqlalchemy import or_

        # 搜索：文件名、提取的数据、内容预览
        return (
            db.query(ExtractionRecord)
            .filter(
                or_(
                    ExtractionRecord.filename.contains(keyword),
                    ExtractionRecord.content_preview.contains(keyword),
                    # 新增：在 extracted_data 的 JSON 中搜索
                    ExtractionRecord.extracted_data.cast(String).contains(keyword),
                )
            )
            .order_by(ExtractionRecord.created_at.desc())
            .limit(20)
            .all()
        )
