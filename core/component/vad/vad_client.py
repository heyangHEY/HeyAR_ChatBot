import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseVADClient(ABC):
    @abstractmethod
    def is_speech(self, frame) -> bool:
        pass

class WebRTCVADClient(BaseVADClient, ABC):
    def __init__(self, config):
        self.config = config

        self.mode: int = config.get("mode", 0)
        self.sample_rate: int = config.get("sample_rate", 16000)
        import webrtcvad
        self.vad = webrtcvad.Vad(self.mode)

    def is_speech(self, frame) -> bool:
        # TODO 检查chunk duration是否时10ms、20ms、30ms这三种
        return self.vad.is_speech(frame, self.sample_rate)
    
# TODO
class SileroVADClient(BaseVADClient, ABC):
    def __init__(self, config):
        self.config = config

        self.mode: int = config.get("mode", 0)
        self.sample_rate: int = config.get("sample_rate", 16000)
        self.vad = None

    def is_speech(self, frame) -> bool:
        return False
