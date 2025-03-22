import time
import logging
from typing import List, Dict, AsyncGenerator
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
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
        logger.debug(f"Ollama LLM 组件初始化完成，耗时: {time.time() - start_time} 秒")

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)
        try:
            response = ""
            async for token in self.llm.astream(messages):
                content = token.content
                if content:
                    response += content.strip()
                    if print_stream:
                        print(content, end="", flush=True)
                    yield content
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

class AsyncOpenAIClient(AsyncBaseLLMClient):
    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.timeout = config.get("timeout", 30)

        self.model_name = config.get("model_name", "")
        self.temperature = config.get("temperature", 0.1)
        self.stream = config.get("stream", True)

        # 初始化OpenAI模型
        self.llm = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout # 请求超时时间，单位为秒
        )
        logger.debug(f"OpenAI LLM 组件初始化完成")

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)
        try:
            response = ""
            generator = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature, # 温度，取值范围[0,1]，0代表确定性输出，1代表随机性输出
                stream=True, # 是否启用流式输出
            )
            # ! 首个 token 的 content 为空，千万不要 break，只需跳过即可
            async for token in generator:
                content = token.choices[0].delta.content
                if content:
                    response += content.strip()
                    if print_stream:
                        print(content, end="", flush=True)
                    yield content
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
