from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv
import requests
from openai import OpenAI
import json

# 加载环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_base_url = os.getenv("OPENAI_API_BASE_URL")
gaode_api_key = os.getenv("GAODE_API_KEY")

# 初始化OpenAI客户端
client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)

def get_weather_data(city: str, weather_type: str = "base") -> Dict[str, Any]:
    """
    调用高德天气API获取天气数据
    :param city: 城市名称（中文）
    :param weather_type: 'base' 获取实时天气，'all' 获取天气预报
    :return: 天气数据字典
    """
    base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": gaode_api_key,
        "city": city,
        "extensions": weather_type,
        "output": "JSON"
    }
    
    response = requests.get(base_url, params=params)
    return response.json()

def format_current_weather(weather_data: Dict[str, Any]) -> str:
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

def format_weather_forecast(weather_data: Dict[str, Any]) -> str:
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

# 定义OpenAI函数
weather_functions = [
    {
        "type": "function",
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
    },
    {
        "type": "function",
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
]
'''
https://platform.openai.com/docs/guides/function-calling?api-mode=chat&example=get-weather&strict-mode=enabled
strict: 是否严格模式，如果为True，则函数调用参数必须与定义的参数完全匹配，否则会报错。opeanai platform 建议使用strict模式。此时，
parameters中的每个对象的additionalProperties 必须为False，properties中的所有字段都必须标记为required。
function call支持模型一次调用多个函数，此时这些调用的严格模式将被关闭。
parallel_tool_calls 设置为 false，则确保只调用0或1个函数。
'''

def handle_weather_query(user_query: str) -> str:
    """处理用户的天气查询请求"""
    # 调用OpenAI进行对话
    messages = [{"role": "user", "content": user_query}]
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        functions=weather_functions,
        function_call="auto"
    )
    
    # 获取返回结果
    message = response.choices[0].message
    
    # 如果调用了函数
    if message.function_call:
        function_name = message.function_call.name
        function_args = json.loads(message.function_call.arguments)
        
        # 根据函数名调用相应的天气查询
        if function_name == "get_current_weather":
            weather_data = get_weather_data(function_args["city"], "base")
            weather_info = format_current_weather(weather_data)
        elif function_name == "get_weather_forecast":
            weather_data = get_weather_data(function_args["city"], "all")
            weather_info = format_weather_forecast(weather_data)
        else:
            return "不支持的查询类型"
        
        # 将天气信息发送给GPT进行自然语言处理
        messages.append({
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": function_name,
                "arguments": message.function_call.arguments
            }
        })
        messages.append({
            "role": "function",
            "name": function_name,
            "content": weather_info
        })
        
        final_response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        
        return final_response.choices[0].message.content
    
    return message.content

if __name__ == "__main__":
    # 测试用例
    test_queries = [
        "深圳现在天气怎么样？",
        "北京未来几天的天气如何？",
        "上海的天气预报",
        "广州今天热不热？"
    ]
    
    for query in test_queries:
        print(f"\n用户问题：{query}")
        print(f"AI回答：{handle_weather_query(query)}")
        print("-" * 50)

"""
用户问题：深圳现在天气怎么样？
AI回答：深圳现在的天气状况是多云，温度为13℃，湿度为84%，风向北，风力小于或等于3级。
--------------------------------------------------

用户问题：北京未来几天的天气如何？
AI回答：北京市未来几天的天气预报如下：

2025-03-29 (周六)：
白天：晴，12℃，西北风1-3级
夜间：晴，1℃，西北风1-3级

2025-03-30 (周日)：
白天：晴，15℃，南风1-3级
夜间：晴，3℃，南风1-3级

2025-03-31 (周一)：
白天：晴，20℃，西南风1-3级
夜间：晴，5℃，西南风1-3级

2025-04-01 (周二)：
白天：多云，20℃，西北风1-3级
夜间：晴，8℃，西北风1-3级

以上是预报内容，请注意适当调整衣物保暖，外出时注意防晒。
--------------------------------------------------

用户问题：上海的天气预报
AI回答：上海未来几天的天气预报如下：

2025年3月29日（周六）：
白天的天气状态是阴，预期温度12℃，风向是西风，风力等级是1-3级。夜晚的天气状态也是阴，预期温度6℃，风向依然是西风，风力等级是1-3级。

2025年3月30日（周日）：
白天的天气状态是阴，预期温度13℃，风向是东风，风力等级是1-3级。夜晚的天气状态还是阴，预期温度7℃，风向是东风，风力等级是1-3级。

2025年3月31日（周一）：
白天的天气状态是阴，预期温度14℃，风向是东南风，风力等级是1-3级。夜晚的天气状态是阴，预期温度8℃，风向是东南风，风力等级是1-3级。

2025年4月1日（周二）：
白天的天气状态是阴，预期温度18℃，风向是东风，风力等级是1-3级。夜晚的天气状态是阴，预期温度9℃，风向是东风，风力等级是1-3级。

请根据天气情况适时调整自己的穿着，注意保暖。
--------------------------------------------------

用户问题：广州今天热不热？
AI回答：今天在广州的温度为10℃，可能会感觉有一点凉。
--------------------------------------------------


"""