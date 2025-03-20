import time
import logging
from typing import List, Dict, AsyncGenerator
from abc import ABC, abstractmethod
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

class AsyncBaseLLMClient(ABC):
    @abstractmethod
    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        pass

class AsyncOllamaClient(AsyncBaseLLMClient):
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

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)
        try:
            response = ""
            async for chunk in self.llm.astream(messages):
                token = chunk.content.strip()
                if token:
                    response += token
                    if print_stream:
                        print(token, end="", flush=True)
                    yield token
                else:
                    break
        except Exception as e:
            logger.error(f"Streaming LLM failed: {str(e)}")
            raise
        finally:
            if print_stream:
                print("\n")
            messages.append({
                "role": "assistant",
                "content": response
            })
