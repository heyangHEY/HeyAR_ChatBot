import os
import json
import asyncio
import logging
from textwrap import dedent
from dotenv import load_dotenv
from openai import AsyncOpenAI
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any, List
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters, types

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler(), # 输出到控制台
        logging.FileHandler('mcp_client.log') # 输出到文件
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
GAODE_API_KEY = os.getenv("GAODE_API_KEY")
GAODE_BASE_URL = os.getenv("GAODE_BASE_URL")

"""
参考：
1. https://github.com/modelcontextprotocol/python-sdk
2. https://zhuanlan.zhihu.com/p/27463359194
    1. 创建 AsyncExitStack 实例：在 __init__ 方法中，创建了一个 AsyncExitStack 实例 self.exit_stack。
    2. 添加异步上下文管理器：在 initialize 方法中，使用 enter_async_context 方法将 stdio_client(server_params) 和 ClientSession(read, write, sampling_callback=self.handle_sampling) 这两个异步上下文管理器添加到 AsyncExitStack 中。
    3. 自动退出上下文：当 AsyncExitStack 退出时（例如，当 initialize 方法执行完毕或者出现异常时），会自动按相反的顺序调用这两个异步上下文管理器的 __aexit__ 方法，确保资源被正确释放。
"""

class MCPClient:
    """MCP客户端类"""
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.system_prompt = dedent( # 去掉了多行字符串的公共前导空白符
                """
                你是一个友好的对话助手。请注意：
                1. 使用口语化表达，避免书面语；
                2. 回答要简短精炼，通常不超过50字，除非用户提出需要详细回答；
                3. 语气要自然亲切，像朋友间对话；
                4. 适时使用语气词增加对话自然度；
                5. 如果用户说话不完整或有噪音，要学会根据上下文理解和确认。
                """
            )
        self.mcp_prompt = ""
        self.tools = []
        self.mcp_session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack() # 堆栈，存储异步上下文，后进先出
        
    async def initialize(self):
        """初始化MCP客户端会话"""
        # 配置MCP服务器参数
        server_params = StdioServerParameters(
            command="python",
            args=["test/9_测试MCP_Server_weather.py"],
            env={"GAODE_API_KEY": GAODE_API_KEY, "GAODE_BASE_URL": GAODE_BASE_URL}, # 给MCP Server传递环境变量
        )
        # # 原来的写法。缺点是离开 initialize 函数后，再次和 MCP Server 会话时需要重新创建上下文。
        # with stdio_client(server_params) as (read, write):
        #     with ClientSession(read, write, sampling_callback=self.handle_sampling) as session:
        #         await session.initialize()

        # ! 使用 enter_async_context 进入 stdio_client 异步上下文管理器
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        # ! 使用 enter_async_context 进入 ClientSession 异步上下文管理器
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write, sampling_callback=None))
        # 比如Server调用删除文件的工具，为了安全，需要MCP Client二次确认。此时MCP Server可以通过create_message()创建消息，MCP Client通过sampling_callback回调获取消息，并进行确认。
        # 参考：https://zhuanlan.zhihu.com/p/27463359194
        await self.mcp_session.initialize()

        # * 提示词
        # 列出所有提示词
        try:
            # ListPromptsRequest
            # meta=None nextCursor=None prompts=[Prompt(name='weather_prompt', description='', arguments=[])]
            prompts: types.ListPromptsResult = await self.mcp_session.list_prompts()
            logger.info(f"可用提示词: {prompts.prompts}")
        except Exception as e:
            logger.warning(f"获取提示词失败: {e}")

        # 获取提示词：system_prompt 和 weather_prompt
        try:
            for prompt in prompts.prompts:
                result: types.GetPromptResult = await self.mcp_session.get_prompt(prompt.name, arguments={})
                if self.mcp_prompt == "":
                    self.mcp_prompt = result.messages[0].content.text
                else:
                    self.mcp_prompt += f"\n{result.messages[0].content.text}"
                logger.info(f"获取 {prompt.name} 提示词成功: {self.mcp_prompt}")
        except Exception as e:
            logger.warning(f"获取提示词失败: {e}")

        # * 资源
        # 列出所有资源
        try:
            # ListResourcesRequest
            # meta=None nextCursor=None resources=[Resource(uri=Url('resource://weather_resource'), name='resource://weather_resource', description=None, mimeType='text/plain', size=None, annotations=None)]
            resources: types.ListResourcesResult = await self.mcp_session.list_resources()
            logger.info(f"可用资源: {resources.resources}")
        except Exception as e:
            logger.warning(f"获取资源失败: {e}")

        # 获取资源: resource://weather_resource
        try:
            for resource in resources.resources:
                # ReadResourceRequest
                # meta=None contents=[TextResourceContents(uri=Url('resource://weather_resource'), mimeType='text/plain', text='\n{WEATHER_RESOURCE}\n')]
                resource_result: types.ReadResourceRequest = await self.mcp_session.read_resource(resource.uri)
                logger.info(f"从 uri: {resource.uri} 处获取资源成功: {resource_result.contents[0].text}")
        except Exception as e:
            logger.warning(f"获取资源失败: {e}")

        # * 工具
        # 列出所有工具
        try:
            # ListToolsRequest
            # meta=None nextCursor=None tools=[Tool(name='get_current_weather', description='', inputSchema={'properties': {'city': {'title': 'city', 'type': 'string'}}, 'required': ['city'], 'title': 'get_current_weatherArguments', 'type': 'object'}), Tool(name='get_weather_forecast', description='', inputSchema={'properties': {'city': {'title': 'city', 'type': 'string'}}, 'required': ['city'], 'title': 'get_weather_forecastArguments', 'type': 'object'})]
            tools_result: types.ListToolsResult = await self.mcp_session.list_tools()
            self.tools = tools_result.tools
            logger.info(f"可用工具: {self.tools}")
            
            # 将MCP工具转换为OpenAI function calling格式
            self.openai_tools = self.convert_to_openai_tools(self.tools)
            logger.info(f"转换成OpenAI function calling格式: {json.dumps(self.openai_tools, ensure_ascii=False, indent=2)}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.warning(f"获取工具列表失败: {e}")

    async def cleanup(self):
        """清理MCP客户端会话"""
        await self.exit_stack.aclose()

    def convert_to_openai_tools(self, mcp_tools: List[types.Tool]) -> List[Dict[str, Any]]:
        """将MCP工具转换为OpenAI function calling格式"""
        openai_tools = []
        
        for mcp_tool in mcp_tools:
            # [Tool(name='get_current_weather', description='', inputSchema={'properties': {'city': {'title': 'city', 'type': 'string'}}, 'required': ['city'], 'title': 'get_current_weatherArguments', 'type': 'object'})]
            tool_name = mcp_tool.name
            tool_description = mcp_tool.description
            tool_parameters = mcp_tool.inputSchema
            
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            required_params = tool_parameters.get("required", [])
            openai_tool["function"]["parameters"]["required"] = required_params
            
            # 添加参数
            for param_name, param_info in tool_parameters.get("properties", {}).items():
                param_type = param_info.get("type", "string")
                param_description = param_info.get("description", "") # mcp server中没有这个参数
                
                openai_tool["function"]["parameters"]["properties"][param_name] = {
                    "type": param_type,
                    "description": param_description
                }
                
            openai_tools.append(openai_tool)
            
        return openai_tools
    
    async def handle_sampling(
        self, message: types.CreateMessageRequestParams
    ) -> types.CreateMessageResult:
        """处理采样回调"""
        pass

    async def process_query(self, query: str) -> str:
        """处理用户消息"""
        logger.info(f"收到用户消息: {query}")
        
        try:
            # 准备完整的系统提示词
            full_system_prompt = f"{self.system_prompt} 你有以下可用工具：{self.mcp_prompt}"
            
            # 准备消息记录
            messages = [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": query}
            ]

            # 调用OpenAI API
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=self.openai_tools if self.openai_tools else None,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            content = assistant_message.content or ""
            stop_reason = response.choices[0].finish_reason
            
            # 检查是否有工具调用
            if assistant_message.tool_calls:
                # 处理工具调用
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"工具调用: {function_name}({function_args})")
                    
                    # 执行MCP工具调用
                    try:
                        result = await self.mcp_session.call_tool(function_name, function_args)
                        
                        if result.isError:
                            logger.warning(f"工具调用失败: {result}")
                            content = f"很抱歉，我在获取信息时遇到了问题。请稍后再试。"
                        else:
                            # 解析工具返回结果
                            tool_result = None
                            for content_item in result.content:
                                if content_item.type == 'text':
                                    tool_result = json.loads(content_item.text)
                                    break
                            
                            # 使用工具返回结果作为新消息，生成最终回复
                            if tool_result and tool_result.get('status') == 'success':
                                tool_message = tool_result.get('message', '')
                                
                                # 将工具结果加入到消息上下文
                                messages.append({"role": "assistant", "content": None, "tool_calls": [
                                    {
                                        "id": tool_call.id,
                                        "type": "function",
                                        "function": {"name": function_name, "arguments": tool_call.function.arguments}
                                    }
                                ]})
                                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_message})
                                
                                # 生成最终回复
                                final_response = await self.openai_client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=messages
                                )
                                content = final_response.choices[0].message.content
                            else:
                                content = "无法获取所需信息，请稍后再试。"
                    except Exception as e:
                        logger.error(f"执行工具调用时出错: {e}")
                        content = "很抱歉，我在处理您的请求时遇到了技术问题。"
            
            return content
            
        except Exception as e:
            logger.error(f"处理用户消息时出错: {e}")
            return "很抱歉，我在处理您的请求时遇到了技术问题。"

async def main():
    """主函数"""
    client = MCPClient()
    try:
        logger.info("启动MCP客户端...")
        await client.initialize()
        logger.info("MCP客户端启动成功")
        # 测试查询
        test_queries = [
            "北京今天的天气怎么样？",
            "上海未来几天的天气如何？",
            "深圳的实时天气情况"
        ]
        
        for query in test_queries:
            print(f"\nUser: {query}")
            result = await client.process_query(query)
            print(f"Assistant: {result}\n")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"运行出错: {str(e)}")
    finally:
        await client.cleanup()
        logger.info("程序退出")

if __name__ == "__main__":
    asyncio.run(main())

"""
python test/9_测试MCP_Client_weather.py

User: 北京今天的天气怎么样？
Assistant: 今天北京是阴天，温度在15度左右，湿度65%，南风三级。感觉有点凉，你出门可以带个薄外套哦。有什么计划吗？


User: 上海未来几天的天气如何？
Assistant: 未来几天上海的天气是这样的：

- 周五：白天阴，29℃；晚上中雨，16℃。带把伞备用哦！
- 周六：小雨转晴，21℃到10℃。天气变化多注意保暖。
- 周日：晴，18℃到12℃。出去玩的话很不错。
- 周一：多云到晴，20℃到13℃。适合户外活动。

需要准备啥别忘了哦~


User: 深圳的实时天气情况
Assistant: 深圳现在是多云，温度22℃，湿度比较高，有点闷哦，东南风不到3级。外出记得带着薄外套，注意防潮哦！有啥计划吗？
"""