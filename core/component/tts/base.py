from abc import ABC, abstractmethod
from typing import AsyncGenerator
class AsyncBaseTTSClient(ABC):
    @abstractmethod
    async def astream_tts(self, text_stream: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        pass

    @abstractmethod
    async def astream_tts_to_file(self, text_stream: AsyncGenerator[str, None], output_path: str) -> None:
        pass
