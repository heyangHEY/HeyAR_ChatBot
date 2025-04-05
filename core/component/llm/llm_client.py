import time
import logging
from typing import List, Dict, AsyncGenerator, Tuple, Optional
from abc import ABC, abstractmethod
from core.tools.handler import ToolHandler
from openai import AsyncOpenAI
from ollama import AsyncClient

logger = logging.getLogger(__name__)

class AsyncBaseLLMClient(ABC):
    @abstractmethod
    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        pass

    async def _handle_tool_call(self, messages: List[Dict[str, str]], tool_name: str, tool_args: str) -> Tuple[bool, str]:
        """处理工具调用并返回工具执行结果"""
        try:
            # 执行函数
            tool_response = self.tool_handler.execute_tool(tool_name, tool_args)
            return True, tool_response
        except Exception as e:
            error_msg = f"Tool call failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _record_assistant_tool_calls(self, messages: List[Dict[str, str]], tool_calls: List[Dict]) -> None:
        """记录助手的工具调用"""
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        })

    def _record_tool_response(self, messages: List[Dict[str, str]], tool_name: str, tool_response: str, tool_call_id: Optional[str] = None) -> None:
        """记录工具调用结果"""
        response_msg = {
            "role": "tool",
            "name": tool_name,
            "content": tool_response
        }
        if tool_call_id is not None:
            response_msg["tool_call_id"] = tool_call_id
        messages.append(response_msg)

class AsyncOllamaClient(AsyncBaseLLMClient):
    def __init__(self, config: dict):
        self.model_name = config.get("model_name", "")
        self.temperature = config.get("temperature", 0.1)
        self.base_url = config.get("base_url", "")
        self.tool_handler = None
        self.tool_definitions = []

        # 初始化本地Ollama模型
        self.llm = AsyncClient()

    def config_tool_call(self, tool_handler: ToolHandler):
        self.tool_handler = tool_handler
        self.tool_definitions = tool_handler.get_tool_definitions()

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)

        try:
            while True:
                response = ""
                buffer = ""
                tool_calls = []
                
                # 调用 Ollama 进行对话
                stream = await self.llm.chat(
                    model=self.model_name,
                    messages=messages,
                    stream=True,
                    tools=self.tool_definitions if self.tool_definitions else None
                )

                async for chunk in stream:
                    message = chunk.get('message', {})
                    
                    # TODO 假设tool_calls字段和content字段是互斥的，如果同时存在，则只处理tool_calls
                    # 检查是否是工具调用
                    if message.get('tool_calls', None):
                        tool_calls.extend(message['tool_calls'])
                        continue

                    # 如果是普通文本响应
                    content = message.get('content', '')
                    if content:
                        buffer += content
                        if any(p in content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
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

                # 如果有工具调用，先记录助手的工具调用
                if tool_calls:
                    self._record_assistant_tool_calls(messages, tool_calls)
                    # 然后处理每个工具调用
                    for tool_call in tool_calls:
                        success, tool_response = await self._handle_tool_call(
                            messages, 
                            tool_call.function.name,
                            tool_call.function.arguments
                        )
                        # 无论成功失败都记录结果
                        self._record_tool_response(messages, tool_call.function.name, tool_response)
                        if not success:
                            yield f"\n工具调用失败：{tool_response}\n"
                            return
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
            if not tool_calls:
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
        self.tool_definitions = []

        # 初始化OpenAI模型
        self.llm = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout # 请求超时时间，单位为秒
        )
        logger.debug("OpenAI LLM 组件初始化完成")

    def config_tool_call(self, tool_handler: ToolHandler):
        self.tool_handler = tool_handler
        self.tool_definitions = tool_handler.get_tool_definitions()

    async def _handle_tool_call(self, messages: List[Dict[str, str]], tool_name: str, tool_args: str, tool_call_id: str) -> Tuple[bool, str]:
        """处理工具调用并返回工具执行结果"""
        try:
            # 执行函数
            tool_response = self.tool_handler.execute_tool(tool_name, tool_args)
            return True, tool_response
        except Exception as e:
            error_msg = f"Tool call failed: {str(e)}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return False, error_msg

    async def astream_chat(self, messages: List[Dict[str, str]], session_id: str, print_stream: bool = False) -> AsyncGenerator[str, None]:
        """与LLM进行对话"""
        if print_stream:
            print("AI: ", end="", flush=True)

        try:
            while True:
                response = ""
                buffer = ""
                tool_calls = []
                current_tool_call = None

                generator = await self.llm.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,          # 温度，取值范围[0,1]，0代表确定性输出，1代表随机性输出
                    stream=True,                           # 是否启用流式输出
                    **({
                        "tools": self.tool_definitions,    # 工具定义
                        "tool_choice": "auto",             # 自动选择是否调用工具
                        "parallel_tool_calls": True,       # 是否并行调用工具
                    } if self.tool_definitions else {})    # 如果存在工具定义，则启用工具调用
                )

                async for chunk in generator:
                    # gpt-4o-mini，chunk.choices 一定几率会返回[]，此时需要跳过
                    if len(chunk.choices) == 0:
                        continue

                    delta = chunk.choices[0].delta
                    
                    # 检查是否是工具调用
                    if delta.tool_calls:
                        tool_call = delta.tool_calls[0]  # 每个chunk只会有一个tool_call
                        
                        # 如果有index，说明是新的tool_call开始
                        if tool_call.index is not None:
                            # 确保tool_calls列表有足够的空间
                            while len(tool_calls) <= tool_call.index:
                                tool_calls.append({
                                    "id": None,
                                    "function": {
                                        "name": None,
                                        "arguments": ""
                                    },
                                    "type": "function"
                                })
                            current_tool_call = tool_calls[tool_call.index]
                        
                        # 更新当前tool_call的信息
                        if tool_call.id:
                            current_tool_call["id"] = tool_call.id
                        if tool_call.function:
                            if tool_call.function.name:
                                current_tool_call["function"]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                current_tool_call["function"]["arguments"] += tool_call.function.arguments
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

                # 如果有工具调用，先记录助手的工具调用
                if tool_calls:
                    self._record_assistant_tool_calls(messages, tool_calls)
                    # 然后处理每个工具调用
                    for tool_call in tool_calls:
                        if not tool_call["id"] or not tool_call["function"]["name"]:
                            continue
                        success, tool_response = await self._handle_tool_call(
                            messages,
                            tool_call["function"]["name"],
                            tool_call["function"]["arguments"],
                            tool_call["id"]
                        )
                        # 无论成功失败都记录结果
                        self._record_tool_response(
                            messages, 
                            tool_call["function"]["name"], 
                            tool_response,
                            tool_call["id"]
                        )
                        if not success:
                            yield f"\n工具调用失败：{tool_response}\n"
                            return
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
            if not tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response
                })
