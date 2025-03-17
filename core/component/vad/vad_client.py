import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseAsyncVADClient(ABC):
    @abstractmethod
    async def is_speech(self, frame) -> bool:
        pass

class AsyncWebRTCVADClient(BaseAsyncVADClient, ABC):
    def __init__(self, config):
        self.config = config

        self.mode: int = config.get("mode", 0)
        self.sample_rate: int = config.get("sample_rate", 16000)
        import webrtcvad
        self.vad = webrtcvad.Vad(self.mode)

    async def is_speech(self, frame) -> bool:
        # TODO 检查chunk duration是否时10ms、20ms、30ms这三种
        return self.vad.is_speech(frame, self.sample_rate)
    
# TODO
class AsyncSileroVADClient(BaseAsyncVADClient, ABC):
    def __init__(self, config):
        self.config = config

        self.mode: int = config.get("mode", 0)
        self.sample_rate: int = config.get("sample_rate", 16000)
        self.vad = None

    async def is_speech(self, frame) -> bool:
        return False


# 通过工厂模式，实现根据查找表，动态实例化语音活动检测（VAD）类
class AsyncVADClientFactory:
    # 类名-类对象 的查找表
    _cls_map = {
        "WebRTCVAD": AsyncWebRTCVADClient,
        "SileroVAD": AsyncSileroVADClient,
    }

    @classmethod    
    def create(cls, name: str, *args, **kwargs) -> BaseAsyncVADClient:
        """根据配置创建VAD客户端实例"""
        client_class = cls._cls_map.get(name, None)
        if client_class is not None:
            logger.info(f"Supported VAD type: {name}")
            return client_class(*args, **kwargs)
        
        logger.critical(f"Unsupported VAD type: {name}")
        raise ValueError(f"Unsupported VAD type: {name}")
