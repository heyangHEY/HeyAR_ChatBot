from abc import ABC, abstractmethod

class BaseAsyncTTSClient(ABC):
    @abstractmethod
    async def generate_audio(self, text: str) -> bytes:
        pass

class AsyncDouBaoTTSClient(BaseAsyncTTSClient):
    def __init__(self, config: dict):
        self.config = config

        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")

    async def generate_audio(self, text: str) -> bytes:
        pass
