from typing import Optional
from core.component.video import AsyncVideoHandler
from core.component.audio import AsyncAudioIOHandler
from core.component.vad import AsyncVADClient
from core.component.asr import AsyncASRClient
from core.component.llm import AsyncLLMClient
from core.component.tts import AsyncTTSClient

class VoiceChatBotService():
    audio_io_handler: Optional[AsyncAudioIOHandler] = None
    vad_client: Optional[AsyncVADClient] = None
    asr_client: Optional[AsyncASRClient] = None
    llm_client: Optional[AsyncLLMClient] = None
    tts_client: Optional[AsyncTTSClient] = None

    async def init(self):
        pass





class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    audio_io_handler: Optional[AsyncAudioIOHandler] = None
    vad_client: Optional[AsyncVADClient] = None
    asr_client: Optional[AsyncASRClient] = None
    llm_client: Optional[AsyncLLMClient] = None
    tts_client: Optional[AsyncTTSClient] = None

    def init(self):
        pass