# any2table_engine/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ==========================================
# 模块 1：文档智能操作交互 (格式排版)
# ==========================================
class Mod1_FormatInput(BaseModel):
    file_path: str = Field(..., description="待排版的原始 Word 文档绝对路径")
    natural_language_cmd: str = Field(..., description="用户的自然语言指令，例如：'把第一段变成红色字体，并且加粗'")

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "./test_data/sample.docx",
                "natural_language_cmd": "将合同第二段加粗，并把标题改为红色"
            }
        }

class Mod1_FormatOutput(BaseModel):
    status: str = Field(..., description="success 或 failed")
    processed_file_path: Optional[str] = Field(None, description="排版修改后的新文件路径")
    message: Optional[str] = Field(None, description="执行结果描述或报错信息")

# ==========================================
# 模块 2：非结构化文档信息提取 (轻量级提取)
# ==========================================
class Mod2_ExtractInput(BaseModel):
    file_path: str = Field(..., description="用户上传的单个文档路径")
    target_entities: List[str] = Field(..., description="想要提取的特定字段，例如：['项目名称', '负责人', '预算']")

class Mod2_ExtractOutput(BaseModel):
    status: str = Field(..., description="success 或 failed")
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="提取出的结构化 JSON 数据")
    message: Optional[str] = Field(None, description="报错信息")

# ==========================================
# 模块 3：表格自定义数据填写 (多源融合填表)
# ==========================================
class Mod3_FusionInput(BaseModel):
    task_id: str = Field(..., description="任务唯一标识")
    workspace_dir: str = Field(..., description="包含1个空模板和N个参考文件的目录")
    user_request: Optional[str] = Field(None, description="用户的附加自然语言要求")

class Mod3_FusionOutput(BaseModel):
    status: str = Field(..., description="success 或 failed")
    task_id: str = Field(...)
    output_excel_path: Optional[str] = Field(None, description="生成的目标文件路径（xlsx 或 docx）")
    warnings: List[str] = Field(default_factory=list, description="算法产生的警告信息")
    error_msg: Optional[str] = Field(None, description="报错信息")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_20260325_001",
                "workspace_dir": "./test_data/COVID-19数据集",
                "user_request": "请填写中国2020年7月的病例数据"
            }
        }