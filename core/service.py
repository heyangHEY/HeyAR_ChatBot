from pydantic import BaseModel
from core.config import ConfigLoader
from typing import Optional
from core.component.video import AsyncVideoHandler
from core.component.audio import AsyncAudioIOHandler
from core.component.vad import BaseAsyncVADClient, AsyncVADClientFactory
from core.component.asr import AsyncASRClient
from core.component.llm import AsyncLLMClient
from core.component.tts import AsyncTTSClient

class VoiceChatBotService():
    config: ConfigLoader

    # audio_io_handler: Optional[AsyncAudioIOHandler] = None
    vad_client: BaseAsyncVADClient = None
    # asr_client: Optional[AsyncASRClient] = None
    # llm_client: Optional[AsyncLLMClient] = None
    # tts_client: Optional[AsyncTTSClient] = None

    def __init__(self, config):
        self.config = config

    async def init(self):
        # 根据配置文件中selected_component指定的模型，来实例化audio/vad/asr/llm/tts
        audio_name, audio_config = self.config.get_audio_config()

        vad_name, vad_config = self.config.get_vad_config()
        self.vad_client = AsyncVADClientFactory.create(vad_name, vad_config)
        
        asr_name, asr_config = self.config.get_asr_config()
        llm_name, llm_config = self.config.get_llm_config()
        tts_name, tts_config = self.config.get_tts_config()






class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    ...

    def init(self):
        pass