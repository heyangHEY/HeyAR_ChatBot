import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseAsyncAudioIOHandler(ABC):
    @abstractmethod
    async def is_speech(self, frame) -> bool:
        pass

# 异步的音频InputStream、OutputStream处理类
class AsyncAudioIOHandler():
    pass

