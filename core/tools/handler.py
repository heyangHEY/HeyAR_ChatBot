import json
from typing import List, Dict, Any
import logging
from core.utils.config import ConfigLoader
from .weather import WeatherTool
from .time_tool import TimeTool

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
        self.available_tools = {}
        # 收集启用工具的函数定义
        self._tool_definitions = []
        
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
                tool_definitions = tool_instance.get_tool_definitions()
                if isinstance(tool_definitions, list):
                    self._tool_definitions.extend(tool_definitions)
                else:
                    self._tool_definitions.append(tool_definitions)
                
                # 注册工具的处理方法
                for tool_def in tool_definitions:
                    tool_name = tool_def.get("function", {}).get("name", "")
                    if not tool_name:
                        logger.warning(f"工具定义缺少name: {tool_def}")
                        continue
                    if hasattr(tool_instance, f"handle_{tool_name}"):
                        self.available_tools[tool_name] = getattr(tool_instance, f"handle_{tool_name}")
                    else:
                        logger.warning(f"工具 {tool_name} 缺少处理方法: handle_{tool_name}")
                        
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.error(f"初始化工具 {tool_name} 失败: {str(e)}")
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取所有注册的工具定义"""
        return self._tool_definitions
    
    def execute_tool(self, tool_name: str, tool_args: str) -> str:
        """执行指定的工具"""
        logger.debug(f"Tool Call, name: {tool_name}, args: {tool_args}")

        if tool_name not in self.available_tools:
            logger.error(f"未知的工具: {tool_name}")
            return f"未知的工具: {tool_name}"
        
        try:
            args = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
            return self.available_tools[tool_name](args)
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {str(e)}")
            return f"工具执行错误: {str(e)}"
    

