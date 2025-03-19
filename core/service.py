import queue
import uuid
import logging
import asyncio
from typing import Optional, List, Dict
from core.utils.config import ConfigLoader
from core.component.video import AsyncVideoHandler
from core.component.audio import AudioHandler
from core.component.factory import ComponentFactory
from core.component.vad import BaseVADClient
from core.component.asr import BaseASRClient
from core.component.llm import AsyncBaseLLMClient
from core.component.tts import AsyncBaseTTSClient

logger = logging.getLogger(__name__)

class VoiceChatBotService():
    config: ConfigLoader

    audio_handler: Optional[AudioHandler] = None
    vad_client: Optional[BaseVADClient] = None
    asr_client: Optional[BaseASRClient] = None
    llm_client: Optional[AsyncBaseLLMClient] = None
    tts_client: Optional[AsyncBaseTTSClient] = None

    chag_log: List[Dict[str, str]] = []

    def __init__(self, config):
        self.config = config

    async def init(self):
        """初始化所有组件"""
        components = await ComponentFactory.create_components(self.config)
        
        self.audio_handler = components['audio']
        self.vad_client = components['vad']
        self.asr_client = components['asr']
        self.llm_client = components['llm']
        self.tts_client = components['tts']

        await self.audio_handler.init()

    async def pipeline(self):
        logger.info("pipeline开始")
        silence_duration = 0
        triggered = False
        speech_chunks: List[bytes] = []
        self.audio_handler.istream_buffer = queue.Queue()  # 清空buffer中的历史数据

        self.chag_log.append({
            "role": "system",
            "content": "你是一个友好的语音对话助手。请注意：\
                1. 使用口语化表达，避免书面语；\
                2. 回答要简短精炼，通常不超过50字；\
                3. 语气要自然亲切，像朋友间对话；\
                4. 适时使用语气词增加对话自然度；\
                5. 如果用户说话不完整或有噪音，要学会根据上下文理解和确认。"
        })
        self.chag_log.append({
            "role": "assistant",
            "content": "你好，我是你的助手，随时为你服务。"
        })
        print("AI: 你好，我是你的助手，随时为你服务。\n")

        while True: 
            try:
                audio_chunk = self.audio_handler.istream_buffer.get()
                if audio_chunk and len(audio_chunk) == 480 * 2:
                    if self.vad_client.is_speech(audio_chunk):
                        logger.debug("VAD detected speech")
                        speech_chunks.append(audio_chunk)
                        triggered = True
                        silence_duration = 0
                    else:
                        silence_duration += 30 # 30ms
                        if triggered and silence_duration > 300:
                            logger.debug("VAD triggered")
                            # 如果已经触发，且连续300ms都没有语音，则粗略的认为用户已经说完话
                            triggered = False
                            silence_duration = 0
                            # 将speech_chunks中的音频块转换为文本
                            _speech_chunks = speech_chunks.copy()
                            speech_chunks = []
                            session_id = str(uuid.uuid4())
                            asr_text = self.asr_client.speech_to_text(_speech_chunks, session_id)
                            _speech_chunks = []
                            logger.info(f"User: {asr_text}")
                            print(f"User: {asr_text}")
                            self.chag_log.append({
                                "role": "user",
                                "content": asr_text
                            })

                            # 等待llm的流式回复
                            # 等待tts的流式转换
                            # 等待扬声器的流式播放

                            async def llm_text_generator(response: str):
                                generator = self.llm_client.astream_chat(self.chag_log, session_id)
                                print("AI: ", end="", flush=True)
                                async for chunk in generator:
                                    if chunk.strip():
                                        response += chunk
                                        print(chunk, end="", flush=True)
                                        yield chunk
                                    else:
                                        break
                                print("\n")
                            
                            llm_response = ""
                            tts_generator = self.tts_client.astream_tts(llm_text_generator(llm_response))
                            await self.audio_handler.astream_play(tts_generator)
                            print(f"AI: {llm_response}")
                            logger.info(f"AI: {llm_response}")
                            self.chag_log.append({
                                "role": "assistant",
                                "content": llm_response
                            })


            except Exception as e:
                logger.error(f"pipeline失败: {str(e)}")
                raise
            await asyncio.sleep(0.01)

        logger.info("pipeline结束")



class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    ...

    def init(self):
        pass