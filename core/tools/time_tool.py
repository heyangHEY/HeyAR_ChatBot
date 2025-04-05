from datetime import datetime
import pytz

class TimeTool:
    """时间日期工具类"""
    
    @staticmethod
    def get_current_time(timezone: str = "Asia/Shanghai", format: str = "YYYY-MM-DD HH:mm:ss") -> str:
        """
        获取指定时区的当前时间
        
        Args:
            timezone (str): 时区名称，默认为"Asia/Shanghai"
            format (str): 时间格式，支持：
                         - "YYYY-MM-DD HH:mm:ss"（默认）
                         - "YYYY-MM-DD"
                         - "HH:mm:ss"
                         - "YYYY年MM月DD日 HH时mm分ss秒"
                         - "YYYY年MM月DD日"
        
        Returns:
            str: 格式化的时间字符串
        """
        try:
            # 获取指定时区的当前时间
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            
            # 根据格式返回时间字符串
            format_map = {
                "YYYY-MM-DD HH:mm:ss": "%Y-%m-%d %H:%M:%S",
                "YYYY-MM-DD": "%Y-%m-%d",
                "HH:mm:ss": "%H:%M:%S",
                "YYYY年MM月DD日 HH时mm分ss秒": "%Y年%m月%d日 %H时%m分%s秒",
                "YYYY年MM月DD日": "%Y年%m月%d日"
            }
            
            if format in format_map:
                return current_time.strftime(format_map[format])
            else:
                return current_time.strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            return f"获取时间失败：{str(e)}"
    
    @staticmethod
    def get_timestamp() -> int:
        """
        获取当前时间戳（Unix时间戳，单位：秒）
        
        Returns:
            int: 当前时间戳
        """
        return int(datetime.now().timestamp())
    
    @staticmethod
    def get_timezone_list() -> list:
        """
        获取所有可用的时区列表
        
        Returns:
            list: 时区名称列表
        """
        return pytz.all_timezones

"""
[
            {
                "name": "get_current_time",
                "description": "获取指定时区的当前时间",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "时区名称，例如：Asia/Shanghai、America/New_York等",
                            "default": "Asia/Shanghai"
                        },
                        "format": {
                            "type": "string",
                            "description": "时间格式，支持：YYYY-MM-DD HH:mm:ss、YYYY-MM-DD、HH:mm:ss、YYYY年MM月DD日 HH时mm分ss秒、YYYY年MM月DD日",
                            "default": "YYYY-MM-DD HH:mm:ss"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_timestamp",
                "description": "获取当前Unix时间戳（单位：秒）",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_timezone_list",
                "description": "获取所有可用的时区列表",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
"""