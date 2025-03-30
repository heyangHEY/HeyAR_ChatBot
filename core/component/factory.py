from typing import Dict, Type, Any, Optional
from core.utils.config import ConfigLoader
from core.component.audio import AudioHandler
from core.component.vad import SileroVADClient, WebRTCVADClient
from core.component.asr import FunASRClient
from core.component.llm import AsyncOllamaClient, AsyncOpenAIClient
from core.component.tts import AsyncDouBaoTTSClient

class ComponentFactory:
    """统一的组件工厂类
    
    用于管理和创建各种组件（VAD、ASR、LLM、TTS等）的实例。
    """
    
    # 组件类型到具体实现类的映射
    _component_registry: Dict[str, Dict[str, Type]] = {
        "VAD": {
            "SileroVAD": SileroVADClient,
            "WebRTCVAD": WebRTCVADClient,
        },
        "ASR": {
            "FunASR": FunASRClient,
        },
        "LLM": {
            "Ollama": AsyncOllamaClient,
            "OpenAI": AsyncOpenAIClient,
        },
        "TTS": {
            "DouBaoTTS": AsyncDouBaoTTSClient,
            "GizwitsTTS": AsyncDouBaoTTSClient,
        }
    }

    @classmethod
    async def create_components(cls, config: ConfigLoader) -> Dict[str, Any]:
        """根据配置文件创建所有需要的组件实例
        
        Args:
            config: ConfigLoader实例，包含所有组件的配置信息
            
        Returns:
            包含所有组件实例的字典，键为组件类型
        """
        components = {}
        
        # 创建AudioHandler
        audio_handler = AudioHandler(config.get_cls_config("AUDIO"))
        components['audio'] = audio_handler
        
        # 创建VAD组件
        vad_name = config.get_cls_name("VAD")
        vad_config = config.get_cls_config("VAD")
        components['vad'] = cls.create("VAD", vad_name, vad_config)
        
        # 创建ASR组件
        asr_name = config.get_cls_name("ASR")
        asr_config = config.get_cls_config("ASR")
        components['asr'] = cls.create("ASR", asr_name, asr_config)
        
        # 创建LLM组件
        llm_name = config.get_cls_name("LLM")
        llm_config = config.get_cls_config("LLM")
        components['llm'] = cls.create("LLM", llm_name, llm_config)
        
        # 创建TTS组件
        tts_name = config.get_cls_name("TTS")
        tts_config = config.get_cls_config("TTS")
        components['tts'] = cls.create("TTS", tts_name, tts_config)
        
        return components

    @classmethod
    def create(cls, component_type: str, name: str, config: Optional[dict] = None) -> Any:
        """创建单个组件实例
        
        Args:
            component_type: 组件类型（如 "VAD", "ASR" 等）
            name: 组件名称
            config: 组件配置
            
        Returns:
            组件实例
            
        Raises:
            ValueError: 当组件类型或名称未注册时
        """
        if component_type not in cls._component_registry:
            raise ValueError(f"未知的组件类型: {component_type}")
            
        component_dict = cls._component_registry[component_type]
        if name not in component_dict:
            raise ValueError(f"未知的{component_type}组件: {name}")
            
        component_class = component_dict[name]
        return component_class(config) if config is not None else component_class()

    @classmethod
    def register_component(cls, component_type: str, name: str, component_class: Type) -> None:
        """注册新的组件实现类
        
        Args:
            component_type: 组件类型（如 "VAD", "ASR" 等）
            name: 组件名称
            component_class: 组件实现类
        """
        if component_type not in cls._component_registry:
            cls._component_registry[component_type] = {}
        cls._component_registry[component_type][name] = component_class

    @classmethod
    def list_components(cls, component_type: str = None) -> Dict[str, list]:
        """列出已注册的组件
        
        Args:
            component_type: 可选，指定要列出的组件类型
            
        Returns:
            包含组件类型和对应实现列表的字典
        """
        if component_type:
            return {component_type: list(cls._component_registry.get(component_type, {}).keys())}
        return {k: list(v.keys()) for k, v in cls._component_registry.items()}
    