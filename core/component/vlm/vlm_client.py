import time
import logging
from typing import List, Dict, AsyncGenerator
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AsyncBaseVLMClient(ABC):
    @abstractmethod
    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str) -> AsyncGenerator[str, None]:
        """与VLM进行对话"""
        pass

# 通过工厂模式，实现根据查找表，动态实例化VLM客户端
class AsyncVLMClientFactory:
    # 类名-类对象 的查找表
    _cls_map = {
        
    }

    @classmethod    
    def create(cls, name: str, *args, **kwargs) -> AsyncBaseVLMClient:
        """根据配置创建VLM客户端实例"""
        client_class = cls._cls_map.get(name, None)
        if client_class is not None:
            logger.info(f"受支持的VLM类型: {name}")
            return client_class(*args, **kwargs)
        
        logger.critical(f"不支持的VLM类型: {name}")
        raise ValueError(f"不支持的VLM类型: {name}")
