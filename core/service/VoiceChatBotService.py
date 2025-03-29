from typing import AsyncGenerator, Optional, Dict, Any
from openai import OpenAI
import os
from dotenv import load_dotenv
from ..tools.handler import ToolHandler

class VoiceChatBotService:
    def __init__(self):
        load_dotenv()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_API_BASE_URL")
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.openai_api_key,
            base_url=self.openai_base_url
        )
        
        # 初始化工具处理器
        self.tool_handler = ToolHandler()
        
        # 初始化消息历史
        self.messages = []
    
    async def chat_stream(self, text_input: str) -> AsyncGenerator[str, None]:
        """处理用户输入并生成回复流"""
        # 添加用户输入到消息历史
        self.messages.append({"role": "user", "content": text_input})
        
        try:
            # 调用OpenAI API进行对话
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=self.messages,
                functions=self.tool_handler.get_function_definitions(),
                function_call="auto",
                stream=True
            )
            
            buffer = ""
            function_name = None
            function_args = ""
            is_function_call = False
            
            async for chunk in response:
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
                if delta.content:
                    buffer += delta.content
                    # 遇到标点或积累足够字符就输出
                    if any(p in delta.content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
                        yield buffer
                        buffer = ""
            
            # 如果是函数调用，执行函数并处理结果
            if is_function_call and function_name:
                # 记录助手的函数调用
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": function_name,
                        "arguments": function_args
                    }
                })
                
                # 执行函数
                function_response = self.tool_handler.execute_function(function_name, function_args)
                
                # 记录函数响应
                self.messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": function_response
                })
                
                # 让GPT处理函数返回的结果
                final_response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=self.messages,
                    stream=True
                )
                
                buffer = ""
                async for chunk in final_response:
                    if chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        if any(p in chunk.choices[0].delta.content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
                            yield buffer
                            buffer = ""
            
            # 输出剩余的buffer
            if buffer:
                yield buffer
        
        except Exception as e:
            yield f"发生错误：{str(e)}"
    
    def reset(self):
        """重置对话历史"""
        self.messages = [] 