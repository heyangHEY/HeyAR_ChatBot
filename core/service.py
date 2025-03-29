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
from core.tools.handler import ToolHandler

logger = logging.getLogger(__name__)

class VoiceChatBotService():
    config: ConfigLoader

    audio_handler: Optional[AudioHandler] = None
    vad_client: Optional[BaseVADClient] = None
    asr_client: Optional[BaseASRClient] = None
    llm_client: Optional[AsyncBaseLLMClient] = None
    tts_client: Optional[AsyncBaseTTSClient] = None

    chag_log: List[Dict[str, str]] = []
    is_ai_speaking: bool = False  # 添加标志位表示AI是否正在说话

    def __init__(self, config):
        self.config = config

    async def init(self):
        """初始化所有组件"""
        components = await ComponentFactory.create_components(self.config)
        
        # 初始化工具处理器
        self.tool_handler = ToolHandler()
        
        self.audio_handler = components['audio']
        self.vad_client = components['vad']
        self.asr_client = components['asr']
        self.llm_client = components['llm']
        self.tts_client = components['tts']

        await self.audio_handler.init()
        await self.tts_client.init()

    async def pipeline(self):
        self.chag_log.append({
            "role": "system",
            "content": "你是一个友好的语音对话助手。请注意：\
                1. 使用口语化表达，避免书面语；\
                2. 回答要简短精炼，通常不超过50字，除非用户提出需要详细回答；\
                3. 语气要自然亲切，像朋友间对话；\
                4. 适时使用语气词增加对话自然度；\
                5. 如果用户说话不完整或有噪音，要学会根据上下文理解和确认。"
        })
        logger.info(self.chag_log)

        print("AI助手已启动，正在聆听...\n")
        logger.info("AI助手已启动，正在聆听...")

        silence_duration = 0
        triggered = False
        speech_chunks: List[bytes] = []
        self.audio_handler.istream_buffer = queue.Queue()  # 清空麦克风buffer中的历史数据
        # 麦克风每次采集的音频块大小
        chunk_size = self.audio_handler.input_config.frames_per_buffer * 2

        while True: 
            try:
                audio_chunk = self.audio_handler.istream_buffer.get()
                if audio_chunk and len(audio_chunk) == chunk_size:
                    if self.vad_client.is_speech(audio_chunk):
                        logger.debug("VAD detected speech")
                        # 如果AI正在说话且检测到用户说话，则中断AI的回复
                        if self.is_ai_speaking:
                            logger.debug("User interrupted AI's speech")
                            # 取消当前正在执行的ai_response_task任务
                            for task in asyncio.all_tasks():
                                if task.get_name() == 'ai_response':  # 检查特定任务名称
                                    task.cancel()
                                    try:
                                        await task
                                    except asyncio.CancelledError:
                                        logger.debug("已取消AI回复任务")
                            
                            self.is_ai_speaking = False
                            continue
                        
                        speech_chunks.append(audio_chunk)
                        triggered = True
                        silence_duration = 0
                    else:
                        if triggered:
                            # TODO check
                            speech_chunks.append(audio_chunk)
                            silence_duration += 30 # 30ms
                            # 如果检测到说话，且随后沉默时间超过300ms，则粗略的认为用户已经说完话
                            if silence_duration > 300:
                                triggered = False
                                silence_duration = 0
                                logger.debug("VAD triggered")

                                # 将speech_chunks中的音频块转换为文本
                                _speech_chunks = speech_chunks.copy()
                                speech_chunks = []
                                session_id = str(uuid.uuid4())
                                asr_text = self.asr_client.speech_to_text(_speech_chunks, session_id)
                                logger.info(f"User: {asr_text}")
                                print(f"User: {asr_text}")
                                self.chag_log.append({
                                    "role": "user",
                                    "content": asr_text
                                })

                                # llm流式回复
                                self.is_ai_speaking = True
                                
                                async def ai_response_task():
                                    try:
                                        llm_generator = self.llm_client.astream_chat(self.chag_log, session_id, print_stream=True)
                                        # 双向流式tts：一边流式的发送llm的text token，一边流式的接收tts的音频片段
                                        tts_generator = self.tts_client.astream_tts(llm_generator)
                                        # 扬声器流式播放
                                        await self.audio_handler.astream_play(tts_generator)
                                    except Exception as e:
                                        logger.error(f"AI response task failed: {str(e)}")
                                    finally:
                                        # 清空扬声器buffer中的历史数据，即使任务被取消也会执行
                                        self.audio_handler.ostream_buffer = queue.Queue() # 清空扬声器buffer中的历史数据
                                        logger.info("AI: " + self.chag_log[-1]["content"])
                                        self.is_ai_speaking = False

                                # 创建异步任务，允许被用户打断
                                asyncio.create_task(ai_response_task(), name='ai_response')

                                # 清空麦克风buffer中堆积的音频块
                                self.audio_handler.istream_buffer = queue.Queue()
                                
            except Exception as e:
                logger.error(f"pipeline失败: {str(e)}")
                raise
            await asyncio.sleep(0.01)


    async def close(self):
        logger.info("pipeline结束")
        await self.audio_handler.cleanup_resource()
        await self.tts_client.close()

class VideoChatBotService():
    video_handler: Optional[AsyncVideoHandler] = None
    ...

    def init(self):
        pass