import time
import logging
from typing import List, Dict, AsyncGenerator
from abc import ABC, abstractmethod
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

class BaseAsyncLLMClient(ABC):
    @abstractmethod
    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        pass

class AsyncOllamaClient(BaseAsyncLLMClient):
    def __init__(self, config: dict):
        self.model_name = config.get("model_name", "")
        self.temperature = config.get("temperature", 0.1)
        self.base_url = config.get("base_url", "")

        # 初始化本地Ollama模型
        start_time = time.time()
        self.llm = ChatOllama(
            model=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url
        )
        logger.debug(f"Ollama模型初始化完成，耗时: {time.time() - start_time} 秒")

        time.sleep(10)

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        response = await self.llm.astream(messages)
        chunk = response.content
        yield chunk


# 通过工厂模式，实现根据查找表，动态实例化LLM客户端
class AsyncLLMClientFactory:
    # 类名-类对象 的查找表
    _cls_map = {
        "Ollama": AsyncOllamaClient,
    }

    @classmethod    
    def create(cls, name: str, *args, **kwargs) -> BaseAsyncLLMClient:
        """根据配置创建LLM客户端实例"""
        client_class = cls._cls_map.get(name, None)
        if client_class is not None:
            logger.info(f"受支持的LLM类型: {name}")
            return client_class(*args, **kwargs)
        
        logger.critical(f"不支持的LLM类型: {name}")
        raise ValueError(f"不支持的LLM类型: {name}")
