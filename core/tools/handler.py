import json
from typing import List, Dict, Any
import logging
from core.utils.config import ConfigLoader
from .weather import WeatherTool

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.tools_list = config.get_tools_list()
        
        # 工具类映射
        self.tool_classes = {
            "Weather": WeatherTool,
            # 在这里添加其他工具类映射
            # "PlayMusic": PlayMusicTool,
        }
        
        # 注册启用的工具
        self.available_functions = {}
        # 收集启用工具的函数定义
        self.function_definitions = []
        
        # 初始化启用的工具
        self._init_tools()
        
    def _init_tools(self):
        """初始化并注册工具"""
        for tool_name in self.tools_list:
            if tool_name not in self.tool_classes:
                logger.warning(f"未知的工具类型: {tool_name}")
                continue
                
            try:
                # 实例化工具
                tool_instance = self.tool_classes[tool_name](self.config)
                
                # 获取工具的函数定义
                tool_definitions = tool_instance.get_function_definitions()
                if isinstance(tool_definitions, list):
                    self.function_definitions.extend(tool_definitions)
                else:
                    self.function_definitions.append(tool_definitions)
                
                # 注册工具的处理方法
                for func_def in tool_definitions:
                    func_name = func_def["name"]
                    if hasattr(tool_instance, f"handle_{func_name}"):
                        self.available_functions[func_name] = getattr(tool_instance, f"handle_{func_name}")
                    else:
                        logger.warning(f"工具 {tool_name} 缺少处理方法: handle_{func_name}")
                        
            except Exception as e:
                logger.error(f"初始化工具 {tool_name} 失败: {str(e)}")
    
    def get_function_definitions(self) -> List[Dict[str, Any]]:
        """获取所有注册的函数定义"""
        return self.function_definitions
    
    def execute_function(self, function_name: str, function_args: str) -> str:
        """执行指定的函数"""
        logger.debug(f"Function Call, name: {function_name}, args: {function_args}")

        if function_name not in self.available_functions:
            logger.error(f"未知的函数: {function_name}")
            return f"未知的函数: {function_name}"
        
        try:
            args = json.loads(function_args) if isinstance(function_args, str) else function_args
            return self.available_functions[function_name](args)
        except Exception as e:
            logger.error(f"执行函数 {function_name} 失败: {str(e)}")
            return f"函数执行错误: {str(e)}"
    

