"""自然语言指令解析服务"""
from typing import Dict, List, Optional
from enum import Enum
from services.llm_extractor import LLMExtractor


class OperationType(Enum):
    """操作类型枚举"""
    EDIT = "edit"           # 编辑：插入、删除、替换文本
    FORMAT = "format"         # 格式：字体、颜色、大小等
    LAYOUT = "layout"        # 排版：对齐、缩进、段落等
    EXTRACT = "extract"       # 提取：提取特定内容
    STRUCTURE = "structure"    # 结构：章节、目录等


class ParsedCommand:
    """解析后的指令结构"""
    def __init__(self, operation_type: OperationType, params: Dict, confidence: float):
        self.operation_type = operation_type
        self.params = params
        self.confidence = confidence


class NLPCommandParser:
    """自然语言指令解析器"""
    
    @staticmethod
    def parse_command(user_input: str, document_content: str = "") -> ParsedCommand:
        """
        解析用户自然语言指令
        
        Args:
            user_input: 用户的自然语言指令
            document_content: 文档内容（用于上下文理解）
            
        Returns:
            ParsedCommand: 解析后的指令
        """
        # 使用 LLM 智能解析和规划指令
        prompt = f"""
你是一个智能文档操作助手。请深入理解用户的自然语言指令，并制定详细的执行计划。

**用户指令：**
{user_input}

**当前文档内容：**
{document_content[:800] if document_content else "空文档"}

**你的任务：**
1. 深度理解用户的真实意图
2. 分析当前文档的状态
3. 制定详细的执行计划
4. 生成需要的内容（如果用户要求生成内容）
5. 确定具体的操作步骤

**返回格式要求：**
必须返回纯 JSON 格式，不要包含任何其他内容。

{{
    "operation_type": "edit|format|layout|extract|structure|general",
    "params": {{
        "action": "具体的操作动作",
        "position": "操作位置",
        "content": "具体内容或生成的内容",
        "details": {{
            "step1": "第一步操作",
            "step2": "第二步操作",
            "step3": "第三步操作"
        }}
    }},
    "confidence": 0.95,
    "reasoning": "你的推理过程"
}}

**重要说明：**
- 如果用户要求"扩容"、"扩展"，理解为需要添加新内容
- 如果用户要求"随便写"、"自己写"，你需要生成符合文档主题的内容
- 如果用户要求"三段"、"五段"，理解为需要生成对应数量的段落，并且每段内容要独立成段
- 对于"扩容成三段"这样的指令，你需要：
  1. 理解用户想要将文档扩展为三段内容
  2. 分析当前文档的主题和风格
  3. 生成三段符合主题的内容
  4. 确保每段内容都有实际意义，不是空洞的重复
  5. 将生成的内容按段落分割，使用换行符分隔
- 对于"删除"操作，你需要：
  1. 理解用户想要删除什么内容
  2. 分析当前文档的内容
  3. 确定要删除的具体内容
  4. 在params中设置action为"delete"，target为要删除的具体内容
- 你需要根据文档主题和风格生成相关内容
- 内容要连贯、有逻辑性、符合专业标准
- 不要依赖硬编码规则，要发挥你的智能理解能力

只返回 JSON，不要其他内容。
"""
        
    
        try:
            import os
            provider = os.getenv("LLM_PROVIDER", "zhipu")
            
            # 直接调用 LLM 进行指令解析
            if provider == "zhipu":
                from zhipuai import ZhipuAI
                client = ZhipuAI(api_key=os.getenv("ZHIPU_API_KEY"))
                
                response = client.chat.completions.create(
                    model="glm-4.7-flash",  # 使用 glm-4.7-flash 模型
                    messages=[
                        {"role": "system", "content": "你是一个文档操作指令解析器，只输出JSON格式的解析结果。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                )
            elif provider == "aliyun":
                import dashscope
                from dashscope import Generation
                dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
                
                response = Generation.call(
                    model="qwen-turbo",
                    messages=[
                        {"role": "system", "content": "你是一个文档操作指令解析器，只输出JSON格式的解析结果。"},
                        {"role": "user", "content": prompt},
                    ],
                    result_format="message",
                    temperature=0.1,
                )
            else:
                raise ValueError(f"未知的模型提供商: {provider}")
            
            # 处理 LLM 响应
            if provider == "zhipu":
                content = response.choices[0].message.content
            else:  # aliyun
                content = response.output.choices[0].message.content
            
            # 清理并解析 JSON
            content = content.replace("```json", "").replace("```", "").strip()
            import json
            parsed_response = json.loads(content)
            
            # 解析操作类型
            operation_type = OperationType(parsed_response.get("operation_type", "edit"))
            params = parsed_response.get("params", {})
            confidence = parsed_response.get("confidence", 0.5)
            
            return ParsedCommand(operation_type, params, confidence)
            
        except Exception as e:
            print(f"LLM 解析失败: {str(e)}")
            # 如果 LLM 解析失败，使用规则引擎作为后备
            return NLPCommandParser._fallback_parse(user_input)
    
    @staticmethod
    def _fallback_parse(user_input: str) -> ParsedCommand:
        """
        规则引擎解析（LLM 失败时的后备方案）
        注意：这只是后备方案，主要依赖 LLM 的智能解析
        """
        user_input_lower = user_input.lower()
        
        # 处理"扩容"、"扩展"等特殊指令
        if any(keyword in user_input_lower for keyword in ["扩容", "扩展", "扩充"]):
            # 提取段落数量
            import re
            paragraph_match = re.search(r'(\d+)段', user_input)
            paragraph_count = int(paragraph_match.group(1)) if paragraph_match else 3
            
            return ParsedCommand(
                OperationType.EDIT,
                {
                    "action": "insert", 
                    "position": "end",
                    "content": f"生成{paragraph_count}段内容",  # 标记需要生成内容
                    "paragraph_count": paragraph_count
                },
                0.7
            )
        
        # 最基本的关键词匹配
        elif any(keyword in user_input_lower for keyword in ["插入", "添加", "增加"]):
            return ParsedCommand(
                OperationType.EDIT,
                {"action": "insert", "content": user_input},
                0.5  # 低置信度，因为这是后备方案
            )
        elif any(keyword in user_input_lower for keyword in ["删除", "移除"]):
            return ParsedCommand(
                OperationType.EDIT,
                {"action": "delete", "target": user_input},
                0.5
            )
        else:
            # 默认作为一般编辑操作
            return ParsedCommand(
                OperationType.EDIT,
                {"action": "general", "content": user_input},
                0.4
            )
    
    @staticmethod
    def get_command_examples() -> List[Dict]:
        """
        获取常用指令示例
        """
        return [
            {
                "category": "编辑操作",
                "examples": [
                    "在文档开头插入标题：项目总结",
                    "删除第三段的内容",
                    "将'项目'替换为'产品'",
                    "在第二段后添加说明文字"
                ]
            },
            {
                "category": "格式操作",
                "examples": [
                    "将标题字体改为14号",
                    "将重要内容加粗显示",
                    "将关键词标红",
                    "将表格字体改为宋体"
                ]
            },
            {
                "category": "排版操作",
                "examples": [
                    "将标题居中对齐",
                    "段落首行缩进2字符",
                    "调整行间距为1.5倍",
                    "将表格居中显示"
                ]
            },
            {
                "category": "提取操作",
                "examples": [
                    "提取所有表格内容",
                    "提取所有图片",
                    "提取所有标题",
                    "提取包含'预算'的段落"
                ]
            },
            {
                "category": "结构操作",
                "examples": [
                    "添加目录",
                    "添加页眉：机密文档",
                    "添加页码",
                    "添加章节分隔线"
                ]
            }
        ]