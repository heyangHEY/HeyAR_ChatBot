"""
测试OpenAI的function call功能。
实现了OpenAI chat completions模式下，同步接口和异步接口的 单/多 函数调用。
以获取天气信息为例，测试了gpt-4、gpt-4o、gpt-4o-mini在不同模型、不同模式下的表现。

测试结果：
1. 同步版本：
    - gpt-4 + functions 可以一次调用一个函数
    - gpt-4 + tools 可以一次调用一个函数
        - gpt-4不支持parallel_tool_calls参数，无法一次调用多个函数
    - gpt-4o/gpt-4o-mini + tools 可以一次调用多个函数
        - gpt-4o、gpt-4o-mini支持parallel_tool_calls参数，可以一次调用多个函数
2. 异步版本：
    - gpt-4o/gpt-4o-mini + tools 可以一次调用多个函数
"""

import os
import json
import asyncio
import aiohttp
import requests
from openai import OpenAI, AsyncOpenAI
from typing import Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_base_url = os.getenv("OPENAI_API_BASE_URL")
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

# opeanai有两个api mode：
# chat completions，旧版，https://platform.openai.com/docs/guides/function-calling?api-mode=chat&example=get-weather&strict-mode=enabled
    # 调用方式：chat.completions.create
# responses，新版，https://platform.openai.com/docs/guides/function-calling?api-mode=responses&example=get-weather&strict-mode=enabled
    # 调用方式：chat.responses.create

# TODO responses模式报错，不知是否openai版本问题
OPENAI_API_MODE = "chat_completions" # "chat_completions" 或 "responses"
OPENAI_MODEL = "gpt-4"
FC_MODE = "tools" # "functions" 或 "tools" 
# chat_completions有两种实现函数调用的方式：
# 1. 使用functions参数，传入函数定义列表
# 2. 使用tools参数，传入工具定义列表

# 实测，gpt-4 无法一次调用多个函数
# ! gpt-4o + tools 可以一次调用多个函数

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

# * 工具定义列表
function_definitions = [
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
        # "strict": True # the 'strict' parameter is only permitted in 'tools' # strict 参数只允许在 tools 中使用
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
    # 初始化OpenAI客户端
    client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
    # 调用OpenAI进行对话
    chat_log = [
        {
            "role": "system", 
            "content": "你是一个很有帮助的助手。如果用户提问关于实时天气的问题，请调用 ‘get_current_weather’ 函数;如果用户提问关于未来天气的问题，请调用‘get_weather_forecast’函数。请以友好的语气回答问题。"
        },
        {"role": "user", "content": user_query}
    ]
    
    if OPENAI_API_MODE == "chat_completions":
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=chat_log,
            **{
                "functions": function_definitions,
                "function_call": "auto",
            } if FC_MODE == "functions" else {
                "tools": tool_definitions,
                # "auto": 默认，自动调用零个、一个或多个函数
                # "required": 必须调用一个或多个函数
                # '{"type": "function", "name": "get_current_weather"}': 只调用一个特定函数
                # "none": 不调用任何函数
                "tool_choice": "auto",
                # tool_choice="auto"或"required"时，模型可能会选择一次调用多个函数，
                # 设置parallel_tool_calls=False，禁止一次调用多个函数
                "parallel_tool_calls": True # gpt-4 不支持这个参数，gpt-4o 支持
            }
        )
    # elif OPENAI_API_MODE == "responses":
    #     response = client.responses.create(
    #         ...
    #     )
    
    # 获取返回结果
    message = response.choices[0].message

    # FC_MODE == "functions"
    # if message.function_call:
    #     print(message.function_call)
    #     function_name = message.function_call.name
    #     function_args_str = message.function_call.arguments
    #     function_args = json.loads(function_args_str)

    # FC_MODE == "tools"
    if message.tool_calls:
        print(message.tool_calls)
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
        city = json.loads(args)["city"]
        if name == "get_current_weather":
            weather_data = get_weather_data(city, "base")
            weather_info = format_current_weather(weather_data)
        elif name == "get_weather_forecast":
            weather_data = get_weather_data(city, "all")
            weather_info = format_weather_forecast(weather_data)
        else:
            weather_info = json.dumps({"error": "不支持该函数"})
        
        tool_results.append({
            # FC_MODE == "functions"时，role为function
            # FC_MODE == "tools"时，role为tool
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": name,
            "content": weather_info
        })

    chat_log.append({
        "role": "assistant",
        "content": None,
        # FC_MODE == "functions"时，使用function_call
        # FC_MODE == "tools"时，使用tool_calls
        "tool_calls": tool_calls 
    })
    chat_log.extend(tool_results)
    
    final_response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=chat_log
    )
    chat_log.append({
        "role": "assistant",
        "content": final_response.choices[0].message.content
    })
    return final_response.choices[0].message.content

async def handle_weather_query_stream(user_query: str) -> str:
    """处理用户的天气查询请求（流式输出版本）"""
    chat_log = [
        {
            "role": "system", 
            "content": "你是一个很有帮助的助手。如果用户提问关于实时天气的问题，请调用 ‘get_current_weather’ 函数;如果用户提问关于未来天气的问题，请调用‘get_weather_forecast’函数。请以友好的语气回答问题。"
        },
        {"role": "user", "content": user_query}
    ]
    
    try:
        # 初始化异步OpenAI客户端
        client = AsyncOpenAI(api_key=openai_api_key, base_url=openai_base_url)
        
        while True:
            response = ""
            buffer = ""
            tool_calls = []
            current_tool_call = None
            
            # 第一轮对话，获取模型响应
            stream = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=chat_log,
                tools=tool_definitions,
                tool_choice="auto",
                parallel_tool_calls=True,
                stream=True
            )

            """
            用户问题：深圳现在天气怎么样？
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role='assistant', tool_calls=[ChoiceDeltaToolCall(index=0, id='call_tpi6ZotCW5eMtkqpQ5SKvTm1', function=ChoiceDeltaToolCallFunction(arguments='', name='get_current_weather'), type='function')]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='{"', name=None), type=None)]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='city', name=None), type=None)]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='":"', name=None), type=None)]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='深圳', name=None), type=None)]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='"}', name=None), type=None)]), finish_reason=None, index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            ChatCompletionChunk(id='chatcmpl-BIgyWxdxgNnUkSB76IZSeTJj0dSVy', choices=[Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None, tool_calls=None), finish_reason='tool_calls', index=0, logprobs=None)], created=1743794800, model='gpt-4o-2024-08-06', object='chat.completion.chunk', service_tier=None, system_fingerprint='fp_ded0d14823', usage=None)
            """

            async for chunk in stream:
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
                if delta.content:
                    buffer += delta.content
                    if any(p in delta.content for p in ["，", "。", "！", "？", "\n"]) or len(buffer) >= 2:
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
                # 检查工具调用是否完整
                if not tool_call["id"] or not tool_call["function"]["name"] or not tool_call["function"]["arguments"]:
                    continue
                    
                # 根据函数名调用相应的天气查询
                name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])
                city = args["city"]
                
                if name == "get_current_weather":
                    weather_data = await get_weather_data_async(city, "base")
                    weather_info = format_current_weather(weather_data)
                elif name == "get_weather_forecast":
                    weather_data = await get_weather_data_async(city, "all")
                    weather_info = format_weather_forecast(weather_data)
                else:
                    weather_info = json.dumps({"error": "不支持该函数"})
                
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
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
            final_stream = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=chat_log,
                stream=True
            )
            
            final_response = ""
            final_buffer = ""
            
            print("AI回答: ", end="", flush=True)
            async for chunk in final_stream:
                if len(chunk.choices) == 0:
                    continue
                    
                delta = chunk.choices[0].delta
                if delta.content:
                    final_buffer += delta.content
                    if any(p in delta.content for p in ["，", "。", "！", "？", "\n"]) or len(final_buffer) >= 2:
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
[ChatCompletionMessageToolCall(id='call_Qru37CQf72X919EULuvk3ZRj', function=Function(arguments='{"city":"深圳"}', name='get_current_weather'), type='function')]
AI回答：深圳目前的天气是小雨，温度大约是18℃。湿度较高，达到了94%，并且北风微风。如果你计划外出，记得带上雨具哦！
--------------------------------------------------

用户问题：北京未来几天的天气如何？
[ChatCompletionMessageToolCall(id='call_rECE5fQ68BwUmm8xt6NacWW0', function=Function(arguments='{"city":"北京"}', name='get_weather_forecast'), type='function')]
AI回答：北京未来几天的天气情况如下：

- 4月5日（周六）：白天晴，气温22℃，西北风1-3级；夜间晴，气温8℃。
- 4月6日（周日）：白天晴，气温25℃，南风1-3级；夜间多云，气温8℃。
- 4月7日（周一）：白天多云，气温26℃，东北风1-3级；夜间晴，气温10℃。
- 4月8日（周二）：白天多云，气温19℃，南风1-3级；夜间阴，气温11℃。

希望这能帮助你计划未来几天的行程！如果有其他问题，请随时告诉我。
--------------------------------------------------

用户问题：四个直辖市的天气怎么样？
[ChatCompletionMessageToolCall(id='call_YCRSd6S79fyD7q83VlzI9oft', function=Function(arguments='{"city": "北京"}', name='get_current_weather'), type='function'), ChatCompletionMessageToolCall(id='call_3rjymjFjDDXoLTcbjCeAe2jp', function=Function(arguments='{"city": "上海"}', name='get_current_weather'), type='function'), ChatCompletionMessageToolCall(id='call_1Gjp0TBMHLAuCl6gDPf67ZH6', function=Function(arguments='{"city": "天津"}', name='get_current_weather'), type='function'), ChatCompletionMessageToolCall(id='call_temIzOdhqSPoCKZ2446QevnU', function=Function(arguments='{"city": "重庆"}', name='get_current_weather'), type='function')]
AI回答：北京市的实时天气是晴天，温度为10°C，湿度26%，北风，风力≤3级。

上海市目前是阴天，气温14°C，湿度76%，西北风，风力≤3级。

天津市也是晴天，温度为10°C，湿度29%，西北风，风力≤3级。

重庆市现在天气有雾，温度16°C，湿度84%，东北风，风力≤3级。

希望这些信息能帮到你！如果有其他问题，请随时告诉我哦。
--------------------------------------------------

用户问题：北京、上海今天的天气怎么样？
[ChatCompletionMessageToolCall(id='call_TuNX8vQb3caBSVa68DkB9Nst', function=Function(arguments='{"city": "北京"}', name='get_current_weather'), type='function'), ChatCompletionMessageToolCall(id='call_8N7UhHzkoTtTW1YZ3ovTtH4L', function=Function(arguments='{"city": "上海"}', name='get_current_weather'), type='function')]
AI回答：北京今天的天气是晴朗的，气温大约是10℃，湿度为26%，北风微风不超过3级。而在上海，今天是阴天，气温大约是14℃，湿度较高，达到76%，并且是西北风，风力同样不超过3级。希望这些信息对你有所帮助！如果有其他问题，随时问我哦！
--------------------------------------------------

用户问题：广州今天出门需要带伞吗？
[ChatCompletionMessageToolCall(id='call_6M3ZrIaV4cplMDctphFgJhy4', function=Function(arguments='{"city":"广州"}', name='get_weather_forecast'), type='function')]
AI回答：今天广州市的天气预报是白天和晚上都可能有小雨，所以建议您出门时带伞哦！希望您有个愉快的一天。
--------------------------------------------------

"""


"""
异步版本

用户问题：深圳现在天气怎么样？
AI回答: 深圳现在的小雨天气，温度大约是18°C，湿度较高，约为94%。风来自北方，风力不大，大约在3级以下。记得出门带伞哦！

--------------------------------------------------

用户问题：北京未来几天的天气如何？
AI回答: 在未来几天，北京的天气情况如下：

- **4月5日 (周六)**: 白天是晴天，最高温度22℃，西北风1-3级；夜间也会是晴天，最低温度8℃。
- **4月6日 (周日)**: 白天依然晴朗，最高气温25℃，南风1-3级；夜间则变为多云，最低温度8℃。
- **4月7日 (周一)**: 白天将是多云的天气，气温上升至26℃，东北风1-3级；夜晚转晴，气温降至10℃。
- **4月8日 (周二)**: 白天继续多云，气温稍微降至19℃，南风1-3级；夜间转为阴天，最低气温11℃。

希望这能帮到你做好准备哦！

--------------------------------------------------

用户问题：四个直辖市的天气怎么样？
AI回答: 当然可以，以下是四个直辖市的实时天气状况：

- **北京市**：今天天气状况为晴，气温约为10°C，湿度为26%。风向来自北方，风力≤3级。

- **上海市**：今天是阴天，气温约14°C，湿度为76%。西北方向来的微风，风力≤3级。

- **天津市**：天津今天也是晴天，气温约10°C，湿度29%。有西北方向的轻风，风力≤3级。

- **重庆市**：目前重庆有雾，气温约16°C，湿度84%。东北风吹过，风力≤3级。

希望这些信息对你有帮助！如果有什么想了解的，随时问我哦！

--------------------------------------------------

用户问题：北京、上海今天的天气怎么样？
AI回答: 北京今天的天气状况是晴天，当前气温大约为10℃，湿度26%，风向为北风，并且风力较小，不超过3级。

上海今天的天气状况是阴天，气温大约是14℃，湿度较高，为76%，风向为西北风，风力同样是不超过3级。

希望这些信息对你有帮助！

--------------------------------------------------

用户问题：广州今天出门需要带伞吗？
AI回答: 今天广州市的天气状况是雾，温度在16℃，湿度较高，为95%。目前没有降雨的信息，但因为高湿度和雾气，建议您出门时还是带把伞以防万一。另外，注意交通安全哦！

--------------------------------------------------
"""
