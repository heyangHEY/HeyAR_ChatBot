"""
测试Ollama的qwen2.5模型，使用function call功能。
实现了Ollama的同步接口和异步接口的 单/多 函数调用。
以获取天气信息为例，测试了qwen2.5在不同模型、不同模式下的表现。
"""

import os
import json
import asyncio
import aiohttp
import requests
from typing import Dict, Any
from dotenv import load_dotenv
import ollama

# 加载环境变量
load_dotenv()
gaode_api_key = os.getenv("GAODE_API_KEY")

# 创建一个全局的 aiohttp session
async def get_aiohttp_session():
    return aiohttp.ClientSession()

def get_weather_data(city: str, weather_type: str = "base") -> Dict[str, Any]:
    """
    同步版本：调用高德天气API获取天气数据
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

async def get_weather_data_async(city: str, weather_type: str = "base") -> Dict[str, Any]:
    """
    异步版本：调用高德天气API获取天气数据
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
    
    session = await get_aiohttp_session()
    async with session:
        async with session.get(base_url, params=params) as response:
            return await response.json()
        
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

# * 函数定义列表
tool_definitions = [
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

def handle_weather_query(user_query: str) -> str:
    """处理用户的天气查询请求"""
    # 调用OpenAI进行对话
    chat_log = [
        {
            "role": "system", 
            "content": "你是一个很有帮助的助手。如果用户提问关于实时天气的问题，请调用 ‘get_current_weather’ 函数;如果用户提问关于未来天气的问题，请调用‘get_weather_forecast’函数。请以友好的语气回答问题。"
        },
        {"role": "user", "content": user_query}
    ]
    
    response = ollama.chat(
        model="qwen2.5:32b",
        messages=chat_log,
        tools = tool_definitions,
        # stream=True # 流式输出
    )
    print(response)
    # message=Message(
    #     role='assistant', 
    #     content='', 
    #     images=None, 
    #     tool_calls=[
    #         ToolCall(function=Function(name='get_current_weather', arguments={'city': '北京'})), 
    #         ToolCall(function=Function(name='get_current_weather', arguments={'city': '上海'}))
    #     ]
    # )
    # 获取返回结果
    message = response.message

    if message.get("tool_calls", None):
        tool_calls = message.tool_calls
    else:
        # 没有调用函数，直接返回结果
        chat_log.append({
            "role": "assistant",
            "content": message.content
        })
        return message.content
        
    tool_results = []
    for tool_call in tool_calls:
        # 根据函数名调用相应的天气查询
        name = tool_call.function.name
        args = tool_call.function.arguments
        if name == "get_current_weather":
            weather_data = get_weather_data(args["city"], "base")
            weather_info = format_current_weather(weather_data)
        elif name == "get_weather_forecast":
            weather_data = get_weather_data(args["city"], "all")
            weather_info = format_weather_forecast(weather_data)
        else:
            weather_info = json.dumps({"error": "不支持该函数"})
        
        tool_results.append({
            "role": "tool",
            "name": name,
            "content": weather_info
        })

    chat_log.append({
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls 
    })
    chat_log.extend(tool_results)
    
    final_response = ollama.chat(
        model="qwen2.5:32b",
        messages=chat_log
    )
    chat_log.append({
        "role": "assistant",
        "content": final_response.message.content
    })
    return final_response.message.content
    
async def handle_weather_query_stream(user_query: str) -> str:
    """处理用户的天气查询请求（流式输出版本）"""
    # 调用OpenAI进行对话
    chat_log = [
        {
            "role": "system", 
            "content": "你是一个很有帮助的助手。如果用户提问关于实时天气的问题，请调用 ‘get_current_weather’ 函数;如果用户提问关于未来天气的问题，请调用‘get_weather_forecast’函数。请以友好的语气回答问题。"
        },
        {"role": "user", "content": user_query}
    ]
    
    try:
        while True:
            response = ""
            buffer = ""
            tool_calls = []
            
            # 第一轮对话，获取模型响应
            stream = await ollama.AsyncClient().chat(
                model="qwen2.5:32b",
                messages=chat_log,
                tools=tool_definitions,
                stream=True
            )

            """
            model='qwen2.5:32b' created_at='2025-04-04T20:36:39.384864357Z' done=False done_reason=None total_duration=None load_duration=None prompt_eval_count=None prompt_eval_duration=None eval_count=None eval_duration=None message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_weather_forecast', arguments={'city': '北京'}))])
            model='qwen2.5:32b' created_at='2025-04-04T20:36:39.941950815Z' done=False done_reason=None total_duration=None load_duration=None prompt_eval_count=None prompt_eval_duration=None eval_count=None eval_duration=None message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_weather_forecast', arguments={'city': '上海'}))])
            model='qwen2.5:32b' created_at='2025-04-04T20:36:39.994734927Z' done=True done_reason='stop' total_duration=1209921495 load_duration=10492974 prompt_eval_count=276 prompt_eval_duration=62000000 eval_count=44 eval_duration=1132000000 message=Message(role='assistant', content='', images=None, tool_calls=None)
            """

            async for chunk in stream:
                message = chunk.get('message', {})
                
                # 检查是否是工具调用
                if message.tool_calls:
                    tool_calls.extend(message['tool_calls'])
                    continue
                
                # 如果是普通文本响应
                content = message.get('content', '')
                if content:
                    buffer += content
                    if any(p in content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
                        print(buffer, end="", flush=True)
                        response += buffer
                        buffer = ""
            
            # 处理剩余的buffer
            if buffer:
                print(buffer, end="", flush=True)
                response += buffer
            
            # 如果没有工具调用，直接返回结果
            if not tool_calls:
                chat_log.append({
                    "role": "assistant",
                    "content": response
                })
                return response
            
            # 处理工具调用
            tool_results = []
            for tool_call in tool_calls:
                # 根据函数名调用相应的天气查询
                name = tool_call.function.name
                args = tool_call.function.arguments
                city = args["city"]
                
                if name == "get_current_weather":
                    weather_data = get_weather_data(city, "base")
                    weather_info = format_current_weather(weather_data)
                elif name == "get_weather_forecast":
                    weather_data = get_weather_data(city, "all")
                    weather_info = format_weather_forecast(weather_data)
                else:
                    weather_info = json.dumps({"error": "不支持该函数"})
                
                tool_results.append({
                    "role": "tool",
                    "name": name,
                    "content": weather_info
                })
            
            # 记录工具调用和结果
            chat_log.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls
            })
            chat_log.extend(tool_results)
            
            # 第二轮对话，让模型总结结果
            final_stream = await ollama.AsyncClient().chat(
                model="qwen2.5:32b",
                messages=chat_log,
                stream=True
            )
            
            final_response = ""
            final_buffer = ""

            async for chunk in final_stream:
                message = chunk.get('message', {})
                content = message.get('content', '')
                if content:
                    final_buffer += content
                    if any(p in content for p in ["，", "。", "！", "？", "\n"]) or len(final_buffer) >= 2:
                        print(final_buffer, end="", flush=True)
                        final_response += final_buffer
                        final_buffer = ""
            
            # 处理剩余的buffer
            if final_buffer:
                print(final_buffer, end="", flush=True)
                final_response += final_buffer
            
            chat_log.append({
                "role": "assistant",
                "content": final_response
            })
            return final_response
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        return f"处理请求时出错：{str(e)}"
    finally:
        print("\n")

if __name__ == "__main__":
    # 测试用例
    test_queries = [
        "深圳现在天气怎么样？",
        "北京未来几天的天气如何？",
        "四个直辖市的天气怎么样？", # ! 测试一次调用多个函数
        "北京、上海今天的天气怎么样？",
        "广州今天出门需要带伞吗？",
    ]
    
    print("同步版本")
    for query in test_queries:
        print(f"\n用户问题：{query}")
        print(f"AI回答：{handle_weather_query(query)}")
        print("-" * 50)

    print("异步版本")
    async def run_tests():
        for query in test_queries:
            print(f"\n用户问题：{query}")
            response = await handle_weather_query_stream(query)
            print("-" * 50)
    
    asyncio.run(run_tests())

"""
同步版本

用户问题：深圳现在天气怎么样？
model='qwen2.5:32b' created_at='2025-04-04T20:53:32.461204427Z' done=True done_reason='stop' total_duration=644398942 load_duration=10113303 prompt_eval_count=274 prompt_eval_duration=68000000 eval_count=21 eval_duration=561000000 message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_current_weather', arguments={'city': '深圳'}))])
AI回答：深圳现在的天气是小雨，温度为18℃，湿度高达94%，风向朝北，风力较弱（小于或等于3级）。这些信息的发布时间是2025-04-05 04:30:16。记得带伞哦！
--------------------------------------------------

用户问题：北京未来几天的天气如何？
model='qwen2.5:32b' created_at='2025-04-04T20:53:34.970390216Z' done=True done_reason='stop' total_duration=646621382 load_duration=9276012 prompt_eval_count=276 prompt_eval_duration=62000000 eval_count=22 eval_duration=569000000 message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_weather_forecast', arguments={'city': '北京'}))])
AI回答：北京未来几天的天气预报如下：

- 2025年4月5日（星期6）: 白天是晴朗的，气温达到22℃，有西北风1-3级；夜间依然保持晴朗，气温降至8℃，风力不变。
  
- 2025年4月6日（星期7）: 白天继续晴朗，温度上升到25℃，转为南风1-3级；夜晚天气变为多云，气温降到8℃，有轻微的南风。

- 2025年4月7日（星期1）: 全天大部分时间是多云状态，白天最高温度达到26℃，东北风1-3级；夜间转为晴朗，最低温度大约在10℃左右，东北风同样维持1-3级。

- 2025年4月8日（星期2）: 白天依旧是多云的天气，气温稍低至19℃，有南风1-3级；夜间变为阴天，温度降至11℃，南风依旧为1-3级。

请您根据这些信息做好出行和穿衣安排！
--------------------------------------------------

用户问题：四个直辖市的天气怎么样？
model='qwen2.5:32b' created_at='2025-04-04T20:53:45.939155919Z' done=True done_reason='stop' total_duration=4137735861 load_duration=9953311 prompt_eval_count=275 prompt_eval_duration=61000000 eval_count=158 eval_duration=4062000000 message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_current_weather', arguments={'city': '北京'})), ToolCall(function=Function(name='get_current_weather', arguments={'city': '天津'})), ToolCall(function=Function(name='get_current_weather', arguments={'city': '上海'})), ToolCall(function=Function(name='get_current_weather', arguments={'city': '重庆'}))])
AI回答：当前四个直辖市的天气情况如下：

- **北京**：
   - 天气状况：晴朗。
   - 温度：9℃，湿度较低（27%）。
   - 风向为西北方向，风力≤3级。

- **天津**：
   - 天气状况：晴朗。
   - 温度：10℃，湿度稍低（28%）。
   - 风从北方来，风力≤3级。

- **上海**：
   - 天气状况：阴天。
   - 温度：14℃，湿度较高（77%），天气较为湿润。
   - 风向为北方向，风力同样≤3级。

- **重庆**：
   - 天气状况：有雾出现。
   - 温度：16℃，湿度很高（85%）。
   - 风从西北吹来，风力也是≤3级。 

以上信息的发布时间为2025年4月5日的凌晨四点左右，请注意实时天气变化。
--------------------------------------------------

用户问题：北京、上海今天的天气怎么样？
model='qwen2.5:32b' created_at='2025-04-04T20:53:56.140124667Z' done=True done_reason='stop' total_duration=3379939498 load_duration=9557694 prompt_eval_count=276 prompt_eval_duration=62000000 eval_count=129 eval_duration=3303000000 message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_weather_forecast', arguments={'city': '北京'})), ToolCall(function=Function(name='get_weather_foreast', arguments={'city': '上海'})), ToolCall(function=Function(name='get_weather_forecast', arguments={'city': '上海'}))])
AI回答：看来我们能够获取到北京和上海的未来天气预报信息。

对于北京市，今天的天气将是晴朗，日间温度将达到22℃，夜间则降至8℃。接下来几天中，总体上会是晴或多云的天气，温差也会保持在类似的范围内。

而对于上海市，今天预计是阴天，白天最高气温为23℃，夜晚最低气温11℃。随后几天里，上海的天气将交替出现在多云和阴之间，气温也大致在这个区间内波动。

如果您需要更加详细的信息或者有其他城市的天气问题，请随时告诉我！
--------------------------------------------------

用户问题：广州今天出门需要带伞吗？
model='qwen2.5:32b' created_at='2025-04-04T20:54:00.469340993Z' done=True done_reason='stop' total_duration=626588283 load_duration=9991484 prompt_eval_count=277 prompt_eval_duration=63000000 eval_count=21 eval_duration=548000000 message=Message(role='assistant', content='', images=None, tool_calls=[ToolCall(function=Function(name='get_current_weather', arguments={'city': '广州'}))])
AI回答：广州现在的天气情况是雾，温度为16℃。虽然没有提到下雨，但因为湿度达到95%，如果你现在出门，携带一把伞可能会让你更舒适一些，伞可以帮助抵挡湿气和偶尔可能的轻微降水。祝你今天愉快！
--------------------------------------------------

"""


"""
异步版本

用户问题：深圳现在天气怎么样？
深圳当前的天气情况是小雨，温度为18℃，湿度较高达到94%，风向来自北方，风力较弱不超过3级。这些信息是在2025年4月5日04:30:16发布的。记得带伞哦！

--------------------------------------------------

用户问题：北京未来几天的天气如何？
北京未来几天的天气预报如下：

- 2025年4月5日（星期六）: 白天晴朗，气温约为22°C，有西北风；夜间也保持晴朗，气温降至8°C。
- 2025年4月6日（星期日）: 全天气温较高，白天最高温度可达25°C，并且是晴转多云的天气，南风吹拂。
- 2025年4月7日（星期一）: 多云到晴天转变，白天气温可升至26°C，晚上气温下降至10°C左右，东北风轻吹。
- 2025年4月8日（星期二）: 白天多云，气温有所回落，最高温度为19°C；夜间阴转，温度为11°C。

请注意带好适合的衣物，并随时关注天气变化。

--------------------------------------------------

用户问题：四个直辖市的天气怎么样？
目前四个直辖市的天气情况如下：

- **北京**：
    - 天气状况：晴朗，温度为9℃，湿度27%，风向西北风，风力小于等于3级。
  
- **上海**：
    - 天气状况：阴天，温度为14℃，湿度77%，风向北风，风力小于等于3级。

- **广州**（注意：广州并非直辖市，但您可能是指包含在内的主要城市）：
    - 天气状况：有雾，温度为16℃，湿度95%，风向北风，风力小于等于3级。
  
- **深圳**（同样地，深圳也不是直辖市）：
    - 天气状况：小雨，温度为18℃，湿度94%，风向北风，风力小于等于3级。

以上信息的发布时间分别为2025年4月5日的不同时间点。希望这些信息对您有帮助！

--------------------------------------------------

用户问题：北京、上海今天的天气怎么样？
今天北京市的实时天气是晴朗，气温为9℃，湿度较低，仅为27%，并且有西北方向的微风。而上海市则是阴天，气温稍高一些，达到了14℃，但同时湿度也较高，达到77%，同样也有轻微的北向风。以上信息都是最新发布的数据，请根据这些信息做好出行准备！

--------------------------------------------------

用户问题：广州今天出门需要带伞吗？
广州当前的天气是雾，湿度非常大，达到了95%，虽然没有提到是否在下雨，但因为有雾且湿度很大，如果避免衣服潮湿或者遇到突发降雨，带把伞会是个不错的选择。

"""