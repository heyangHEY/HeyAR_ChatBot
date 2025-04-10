from typing import Dict, Any, List
import requests
from core.utils.config import ConfigLoader
import logging

logger = logging.getLogger(__name__)

class WeatherTool:
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.api_key = config.get_tool_config("Weather").get("Gaode", "api_key")
        self.base_url = config.get_tool_config("Weather").get("Gaode", "base_url")

        # 定义天气相关的函数
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "获取指定城市的实时天气信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "中国城市名称，例如：北京、上海、深圳"
                            }
                        },
                        "required": ["city"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather_forecast",
                    "description": "获取指定城市的未来天气预报（今天及未来3天）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "中国城市名称，例如：北京、上海、深圳"
                            }
                        },
                        "required": ["city"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
        ]

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取所有注册的函数定义"""
        return self.tool_definitions

    def _get_weather_data(self, city: str, weather_type: str = "base") -> Dict[str, Any]:
        """
            调用高德天气API获取天气数据
            :param city: 城市名称（中文）
            :param weather_type: 'base' 获取实时天气，'all' 获取天气预报
            :return: 天气数据字典
        """
        if not self.api_key:
            raise ValueError("高德API密钥未配置")
        params = {
            "key": self.api_key,  
            "city": city,
            "extensions": weather_type,
            "output": "JSON"
        }
        
        response = requests.get(self.base_url, params=params)
        return response.json()

    def _format_current_weather(self, weather_data: Dict[str, Any]) -> str:
        """格式化实时天气信息"""
        if weather_data["status"] != "1" or weather_data["infocode"] != "10000":
            return f"查询失败：{weather_data.get('info', '未知错误')}"
        
        live = weather_data["lives"][0]
        return (
            f'{live["province"]}{live["city"]}的实时天气：\n'
            f'天气状况：{live["weather"]}\n'
            f'温度：{live["temperature"]}℃\n'
            f'湿度：{live["humidity"]}%\n'
            f'风向：{live["winddirection"]}\n'
            f'风力：{live["windpower"]}级\n'
            f'发布时间：{live["reporttime"]}'
        )

    def _format_weather_forecast(self, weather_data: Dict[str, Any]) -> str:
        """格式化天气预报信息"""
        if weather_data["status"] != "1" or weather_data["infocode"] != "10000":
            return f"查询失败：{weather_data.get('info', '未知错误')}"
        
        forecast = weather_data["forecasts"][0]
        result = f'{forecast["province"]}{forecast["city"]}未来天气预报：\n'
        
        for cast in forecast["casts"]:
            result += (
                f'\n{cast["date"]} (周{cast["week"]})：\n'
                f'白天：{cast["dayweather"]}，{cast["daytemp"]}℃，{cast["daywind"]}风{cast["daypower"]}级\n'
                f'夜间：{cast["nightweather"]}，{cast["nighttemp"]}℃，{cast["nightwind"]}风{cast["nightpower"]}级\n'
            )
        return result

    def handle_get_current_weather(self, args: Dict[str, Any]) -> str:
        """处理实时天气查询"""
        city = args.get("city")
        if not city:
            return "缺少城市参数"
        
        weather_data = self._get_weather_data(city, "base")
        return self._format_current_weather(weather_data)
    
    def handle_get_weather_forecast(self, args: Dict[str, Any]) -> str:
        """处理天气预报查询"""
        city = args.get("city")
        if not city:
            return "缺少城市参数"
        
        weather_data = self._get_weather_data(city, "all")
        return self._format_weather_forecast(weather_data)
