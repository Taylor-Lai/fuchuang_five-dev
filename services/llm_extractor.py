import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv()

# 读取配置
PROVIDER = os.getenv("LLM_PROVIDER", "zhipu")
ZHIPU_KEY = os.getenv("ZHIPU_API_KEY")
ALIYUN_KEY = os.getenv("DASHSCOPE_API_KEY")


class LLMExtractor:
    """大模型信息提取器：支持智谱和通义千问"""

    @staticmethod
    def extract_info(text: str, fields: List[str]) -> Dict:
        """
        从文本中提取指定字段
        :param text: 文档解析后的纯文本
        :param fields: 需要提取的字段列表，如 ["甲方", "乙方", "金额"]
        :return: 提取结果的字典
        """

        # 构造 Prompt (提示词)
        prompt = f"""
        你是一个专业的文档信息提取助手。
        请从以下文本中提取关键信息，并以严格的 JSON 格式返回。
        
        需要提取的字段：{', '.join(fields)}
        
        要求：
        1. 如果找不到某个字段，该字段的值设为 null。
        2. 不要输出任何解释性文字，只输出 JSON 对象。
        3. 确保 JSON 格式合法，可以直接被 Python json.loads() 解析。
        
        文本内容：
        ---
        {text[:3000]}  # 限制长度，防止超长报错
        ---
        
        JSON 输出：
        """

        try:
            if PROVIDER == "zhipu":
                return LLMExtractor._call_zhipu(prompt)
            elif PROVIDER == "aliyun":
                return LLMExtractor._call_aliyun(prompt)
            else:
                raise ValueError(f"未知的模型提供商: {PROVIDER}")

        except Exception as e:
            return {"error": str(e), "raw_text": text[:200]}

    @staticmethod
    def _call_zhipu(prompt: str) -> Dict:
        """调用智谱 GLM-4"""
        from zhipuai import ZhipuAI

        client = ZhipuAI(api_key=ZHIPU_KEY)

        response = client.chat.completions.create(
            model="glm-4-flash",  # 使用快速模型
            messages=[
                {"role": "system", "content": "你是一个JSON提取专家，只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # 低温度，保证输出稳定
        )

        content = response.choices[0].message.content
        # 清理可能存在的 markdown 标记
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)

    @staticmethod
    def _call_aliyun(prompt: str) -> Dict:
        """调用通义千问"""
        import dashscope
        from dashscope import Generation

        dashscope.api_key = ALIYUN_KEY

        response = Generation.call(
            model="qwen-turbo",
            messages=[
                {"role": "system", "content": "你是一个JSON提取专家，只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            result_format="message",
            temperature=0.1,
        )

        if response.status_code == 200:
            content = response.output.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        else:
            raise Exception(f"通义千问调用失败: {response.code}, {response.message}")
