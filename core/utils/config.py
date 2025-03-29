import os
import yaml
from typing import Dict, Any, Optional

class ConfigLoader:
    config_path: str = ""
    all_cfg: Dict[str, Any] = {}
    base_cfg: Dict[str, Any] = {}
    selected_component_cfg: Dict[str, list[Any]] = {}

    def __init__(self, config_path: str):
        """初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.all_cfg: Dict[str, Any] = {}
        self.base_cfg: Dict[str, Any] = {}
        self.selected_component_cfg: Dict[str, list[Any]] = {}
        self._load_config()
        
    def _load_config(self) -> None:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.all_cfg = yaml.safe_load(f)

        self.base_cfg = self.all_cfg.get('base', {})
        self.selected_component_cfg = self.all_cfg.get('selected_component', {})

    def get_all_config(self):
        return self.all_cfg

    def get_base_config(self):
        return self.base_cfg
    
    def get_log_config(self):
        return self.base_cfg.get('log', {})
    
    def get_cls_name(self, cls: str):   
        return self.selected_component_cfg.get(cls, "")

    def get_cls_config(self, cls: str):
        cls_name = self.get_cls_name(cls)
        if cls_name:
            return self.all_cfg.get(cls, {}).get(cls_name, {})
        else:
            return {}
    
    # 获取用户想要启用的工具列表
    def get_tools_list(self) -> list[str]:
        return self.selected_component_cfg.get("TOOLS", {})

    # 注意：启用工具之前，需要先配置好工具的参数
    def get_tool_config(self, name: str):
        return self.all_cfg.get("TOOLS", {}).get(name, {})
