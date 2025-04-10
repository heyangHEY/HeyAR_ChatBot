import os
import aiohttp
import asyncio
import logging
import json
from textwrap import dedent
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler(), # 输出到控制台
        logging.FileHandler('mcp_server.log') # 输出到文件
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("mcp").setLevel(logging.INFO)

# 加载环境变量
load_dotenv()
WEATHER_API_KEY = os.getenv("GAODE_API_KEY")
WEATHER_BASE_URL = os.getenv("GAODE_BASE_URL")

class WeatherService:
    """天气服务类"""
    def __init__(self):
        self.api_key = WEATHER_API_KEY
        self.base_url = WEATHER_BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_weather(self, city: str, weather_type: str = "base") -> dict:
        """异步获取指定城市的天气信息"""
        try:
            params = {
                "key": self.api_key,
                "city": city,
                "extensions": weather_type,
                "output": "JSON"
            }
            
            session = await self._get_session()
            async with session.get(self.base_url, params=params) as response:
                data = await response.json()
                
                if data["status"] != "1" or data["infocode"] != "10000":
                    return {"status": "error", "message": f"查询失败：{data.get('info', '未知错误')}"}
                
                if weather_type == "base":
                    live = data["lives"][0]
                    return {
                        "status": "success",
                        "message": (
                            f"{live['province']}{live['city']}的实时天气：\n"
                            f"天气状况：{live['weather']}\n"
                            f"温度：{live['temperature']}℃\n"
                            f"湿度：{live['humidity']}%\n"
                            f"风向：{live['winddirection']}\n"
                            f"风力：{live['windpower']}级\n"
                            f"发布时间：{live['reporttime']}"
                        )
                    }
                else:  # weather_type == "all"
                    forecast = data["forecasts"][0]
                    forecast_text = f"{forecast['province']}{forecast['city']}未来天气预报：\n"
                    for cast in forecast["casts"]:
                        forecast_text += (
                            f"\n{cast['date']} (周{cast['week']})：\n"
                            f"白天：{cast['dayweather']}，{cast['daytemp']}℃，"
                            f"{cast['daywind']}风{cast['daypower']}级\n"
                            f"夜间：{cast['nightweather']}，{cast['nighttemp']}℃，"
                            f"{cast['nightwind']}风{cast['nightpower']}级\n"
                        )
                    return {"status": "success", "message": forecast_text}
                
        except Exception as e:
            return {"status": "error", "message": f"获取天气信息失败: {str(e)}"}
    
    async def get_current_weather(self, city):
        """异步获取指定城市的实时天气"""
        logger.info(f"MCP Server 调用 get_current_weather({city})")
        return await self.get_weather(city, "base")
    
    async def get_weather_forecast(self, city):
        """异步获取指定城市的天气预报"""
        logger.info(f"MCP Server 调用 get_weather_forecast({city})")
        return await self.get_weather(city, "all")
    
    async def close(self):
        """关闭aiohttp会话"""
        if self._session is not None:
            await self._session.close()
            self._session = None

# 创建FastMCP实例
app = FastMCP("MCP_Server")

WEATHER_RESOURCE = {
    "description": "提供全球主要城市的天气查询服务",
    "capabilities": [
        "查询任意城市的实时天气状况",
        "查询任意城市未来几天的天气预报",
        "提供温度、湿度、风向、风力等详细信息"
    ],
    "usage_examples": [
        "北京今天的天气怎么样？",
        "上海未来三天会下雨吗？",
        "深圳现在的温度是多少？"
    ]
}

class MCP_Server:
    """音乐天气服务器类"""
    def __init__(self):
        self.weather_service = WeatherService()
        
    def register_tools(self):
        """注册所有工具方法"""
        # 参考：https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file
        
        # 注册prompts
        # 提示是可重用的模板，帮助大型语言模型有效地与您的服务器互动
        @app.prompt()
        def weather_prompt() -> str:
            return dedent( # 去掉了多行字符串的公共前导空白符
                """
                [天气查询服务]
                能查询指定城市的实时天气和未来几天的天气预报。
                如果用户询问具体城市的天气，使用天气查询工具获取最新信息。
                实时天气应包含: 天气状况、温度、湿度、风向和风力。
                天气预报应包含: 未来几天的天气状况、温度范围和降水概率。
                始终使用礼貌友好的语气，并在提供天气信息后，根据天气情况提供适当的建议。
                """
            )
        logger.info("天气提示词注册完成")
        
        # 注册resources
        # 资源是您如何将数据暴露给大型语言模型（LLMs）。它们类似于REST API中的GET端点 - 提供数据，但不应执行重大计算或产生副作用。
        @app.resource("resource://weather_resource")
        def weather_resource() -> str:
            """
            提供全球主要城市的天气查询服务
            """
            return dedent(
                f"""
                {json.dumps(WEATHER_RESOURCE, ensure_ascii=False, indent=2)}
                """
            )
        logger.info("天气资源注册完成")
        
        # 天气相关工具
        @app.tool()
        async def get_current_weather(city: str):
            """
            获取指定城市的实时天气信息
            
            Args:
                city: str 中国城市名称，例如：北京、上海、深圳
            Returns:
                dict 实时天气信息
            """
            return await self.weather_service.get_current_weather(city)
        logger.info("get_current_weather 注册完成")
        
        @app.tool()
        async def get_weather_forecast(city: str):
            """
            获取指定城市的未来天气预报（今天及未来3天）
            
            Args:
                city: str 中国城市名称，例如：北京、上海、深圳
            Returns:
                dict 未来天气预报信息
            """
            return await self.weather_service.get_weather_forecast(city)
        logger.info("get_weather_forecast 注册完成")

    async def cleanup_async(self):
        """异步清理资源"""
        await self.weather_service.close()

if __name__ == "__main__":
    logger.info("启动 MCP Server")
    server = MCP_Server()
    server.register_tools()
    app.run(transport="stdio")
    asyncio.run(server.cleanup_async())
    logger.info("MCP Server 关闭")
