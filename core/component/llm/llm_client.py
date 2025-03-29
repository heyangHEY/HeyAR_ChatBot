import time
import logging
from typing import List, Dict, AsyncGenerator, Tuple
from abc import ABC, abstractmethod
from core.tools.handler import ToolHandler
from openai import AsyncOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

class AsyncBaseLLMClient(ABC):
    @abstractmethod
    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        pass

    async def _handle_function_call(self, messages: List[Dict[str, str]], function_name: str, function_args: str) -> Tuple[bool, str]:
        """处理函数调用并返回是否需要继续对话"""
        try:
            # 记录助手的函数调用
            messages.append({
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": function_name,
                    "arguments": function_args
                }
            })

            # 执行函数
            function_response = self.tool_handler.execute_function(function_name, function_args)

            # 记录函数的响应
            messages.append({
                "role": "function",
                "name": function_name,
                "content": function_response
            })

            return True, function_response
        except Exception as e:
            logger.error(f"Function call failed: {str(e)}")
            return False, str(e)

class AsyncOllamaClient(AsyncBaseLLMClient):
    def __init__(self, config: dict):
        self.model_name = config.get("model_name", "")
        self.temperature = config.get("temperature", 0.1)
        self.base_url = config.get("base_url", "")
        self.tool_handler = None
        self.function_definitions = []

        # 初始化本地Ollama模型
        start_time = time.time()
        self.llm = ChatOllama(
            model=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url
        )
        logger.debug(f"Ollama LLM 组件初始化完成，耗时: {time.time() - start_time} 秒")

    def config_function_call(self, tool_handler: ToolHandler):
        self.tool_handler = tool_handler
        self.function_definitions = tool_handler.get_function_definitions()

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
            import traceback
            traceback.print_exc()
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
        self.tool_handler = None
        self.function_definitions = []

        # 初始化OpenAI模型
        self.llm = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout # 请求超时时间，单位为秒
        )
        logger.debug("OpenAI LLM 组件初始化完成")

    def config_function_call(self, tool_handler: ToolHandler):
        self.tool_handler = tool_handler
        self.function_definitions = tool_handler.get_function_definitions()

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)

        try:
            while True:
                response = ""
                buffer = ""
                function_name = None
                function_args = ""
                is_function_call = False

                generator = await self.llm.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,                   # 温度，取值范围[0,1]，0代表确定性输出，1代表随机性输出
                    stream=True,                                    # 是否启用流式输出
                    **({
                        "functions": self.function_definitions,     # 函数定义
                        "function_call": "auto",                    # 自动选择是否调用函数
                    } if self.function_definitions else {})         # 如果存在函数定义，则启用函数调用
                )

                async for chunk in generator:
                    # gpt-4o-mini，chunk.choices 一定几率会返回[]，此时需要跳过
                    if len(chunk.choices) == 0:
                        continue

                    delta = chunk.choices[0].delta

                    # 检查是否是函数调用
                    if delta.function_call:
                        is_function_call = True
                        if delta.function_call.name:
                            function_name = delta.function_call.name
                        if delta.function_call.arguments:
                            function_args += delta.function_call.arguments
                        continue

                    # 如果是普通文本响应
                    # 一定几率 token.choices[0].delta.content 为空，此时需要跳过
                    if delta.content:
                        buffer += delta.content
                        if any(p in delta.content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
                            if print_stream:
                                print(buffer, end="", flush=True)
                            yield buffer
                            response += buffer
                            buffer = ""

                # 处理剩余的buffer
                if buffer:
                    if print_stream:
                        print(buffer, end="", flush=True)
                    yield buffer
                    response += buffer

                # 如果是函数调用，处理函数调用
                if is_function_call and function_name:
                    success, func_response = await self._handle_function_call(
                        messages, function_name, function_args
                    )
                    if not success:
                        yield f"\n函数调用失败：{func_response}\n"
                        break
                else:
                    break

        except Exception as e:
            logger.error(f"Streaming LLM failed: {str(e)}")
            import traceback
            traceback.print_exc() # 打印完整堆栈
            raise
        finally:
            if print_stream:
                print("\n")
            if not is_function_call:
                messages.append({
                    "role": "assistant",
                    "content": response
                })
