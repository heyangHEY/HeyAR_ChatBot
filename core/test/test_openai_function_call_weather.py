from openai import OpenAI
from core.utils.config import ConfigLoader
from core.tools import ToolHandler
import logging
import argparse
from core.utils.logger import setup_logging
logger = logging.getLogger(__name__)

class TestOpenAIFunctionCall:
    def __init__(self, config: ConfigLoader):
        self.config = config
        
        # 获取OpenAI配置
        openai_config = config.get_cls_config("LLM")
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=openai_config.get("api_key"),
            base_url=openai_config.get("base_url")
        )
        
        # 初始化工具处理器
        self.tool_handler = ToolHandler(config)
        
        # 获取模型名称
        self.model = openai_config.get("model", "gpt-4")
        
        # 初始化对话历史
        self.messages = []

    def handle_weather_query(self, user_query: str) -> str:
        """处理用户的天气查询请求"""
        # 调用OpenAI进行对话
        self.messages = [{"role": "user", "content": user_query}]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                functions=self.tool_handler.get_function_definitions(),
                function_call="auto"
            )
            
            # 获取返回结果
            message = response.choices[0].message
            
            # 如果调用了函数
            if message.function_call:
                function_name = message.function_call.name
                function_args = message.function_call.arguments
                
                # 执行函数调用
                weather_info = self.tool_handler.execute_function(function_name, function_args)
                
                # 将函数调用和结果添加到对话历史
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": function_name,
                        "arguments": function_args
                    }
                })
                self.messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": weather_info
                })
                
                # 让GPT处理函数返回的结果
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages
                )
                
                return final_response.choices[0].message.content
            
            return message.content
            
        except Exception as e:
            logger.error(f"处理天气查询失败: {str(e)}")
            return f"查询失败: {str(e)}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yml', help='Path to config file')
    args = parser.parse_args()
    # 读取yaml配置
    config_file = args.config
    config = ConfigLoader(config_file)

    # 设置日志系统
    log_cfg = config.get_log_config()
    setup_logging(log_cfg)

    logger.info("----------开始测试OpenAI Function Call----------")
    version = config.get_all_config().get('version', "")
    logger.info(f'load config file, version: {version}, path: {config_file}')

    # 创建测试实例
    test = TestOpenAIFunctionCall(config)
    
    # 测试用例
    test_queries = [
        "深圳现在天气怎么样？",
        "北京未来几天的天气如何？",
        "上海的天气预报",
        "广州今天热不热？"
    ]
    
    # 运行测试
    for query in test_queries:
        print(f"\n用户问题：{query}")
        print(f"AI回答：{test.handle_weather_query(query)}")
        print("-" * 50)

if __name__ == "__main__":
    main()
