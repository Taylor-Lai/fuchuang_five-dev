"""Shared LLM configuration for DocNexus AI modules."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "zhipu")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_llm_instance = None


def get_chat_llm():
    global _llm_instance
    if _llm_instance is None:
        if LLM_PROVIDER == "zhipu" and ZHIPU_API_KEY:
            try:
                from langchain_community.chat_models import ChatZhipuAI
            except ImportError as exc:
                raise ImportError("使用 zhipu 需要安装 langchain-community: pip install langchain-community") from exc
            _llm_instance = ChatZhipuAI(model="glm-4", api_key=ZHIPU_API_KEY, temperature=0)
        elif OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise ImportError("使用 OpenAI 需要安装 langchain-openai: pip install langchain-openai") from exc
            _llm_instance = ChatOpenAI(
                model=OPENAI_MODEL,
                temperature=0,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL or None,
            )
        else:
            raise ValueError("请在 .env 文件中配置 ZHIPU_API_KEY 或 OPENAI_API_KEY")
    return _llm_instance
