from pydantic import BaseModel
from core.utils.config import ConfigLoader
from typing import Optional
from core.component.video import AsyncVideoHandler
from core.component.audio import AudioIOHandler
from core.component.vad import BaseAsyncVADClient, AsyncVADClientFactory
from core.component.asr import BaseASRClient, ASRClientFactory
from core.component.llm import AsyncLLMClient
from core.component.tts import AsyncTTSClient

class VoiceChatBotService():
    config: ConfigLoader

    audio_io_handler: Optional[AudioIOHandler] = None
    vad_client: Optional[BaseAsyncVADClient] = None
    asr_client: Optional[BaseASRClient] = None
    llm_client: Optional[AsyncLLMClient] = None
    tts_client: Optional[AsyncTTSClient] = None

    def __init__(self, config):
        self.config = config

    async def init(self):
        # 根据配置文件中selected_component指定的模型，来实例化audio/vad/asr/llm/tts
        audio_config = self.config.get_audio_config()
        self.audio_io_handler = AudioIOHandler(audio_config)
        await self.audio_io_handler.init()
        # await self.audio_io_handler.test("recording.wav", 5)

        vad_name = self.config.get_cls_name("VAD")
        vad_config = self.config.get_vad_config()
        self.vad_client = AsyncVADClientFactory.create(vad_name, vad_config)
        
        asr_name = self.config.get_cls_name("ASR")
        asr_config = self.config.get_asr_config()
        self.asr_client = ASRClientFactory.create(asr_name, asr_config)

        llm_name = self.config.get_cls_name("LLM")
        llm_config = self.config.get_llm_config()
        # self.llm_client = AsyncLLMClientFactory.create(llm_name, llm_config)

        tts_name = self.config.get_cls_name("TTS")
        tts_config = self.config.get_tts_config()
        # self.tts_client = AsyncTTSClientFactory.create(tts_name, tts_config)




class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    ...

    def init(self):
        pass