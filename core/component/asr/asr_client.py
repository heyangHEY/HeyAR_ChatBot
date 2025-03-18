import os
import uuid
import torch
import logging
import time
import wave
from typing import List
from funasr import AutoModel
from abc import ABC, abstractmethod
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from core.utils.redirect import redirect_to_logger_low_level

# TODO 若音频输入需要通过网络传播，则可以考虑使用Opus编码代替PCM编码，以降低传输带宽

logger = logging.getLogger(__name__)

class BaseASRClient(ABC):
    @abstractmethod
    def save_audio_to_file(self, audio_data: List[bytes], session_id: str, file_path: str) -> str:
        """将音频数据保存到文件中"""
        pass

    @abstractmethod
    def speech_to_text(self, audio_data: List[bytes], session_id: str) -> str:
        """将音频数据转换为文本"""
        pass

class FunASRClient(BaseASRClient):
    def __init__(self, config: dict):
        self.model_dir = config.get("model_dir", "")
        with redirect_to_logger_low_level(logger):
            self.model = AutoModel(
                model=self.model_dir,
                vad_kwargs={"max_single_segment_time": 30000},
                device="cpu", # "cuda:0" if torch.cuda.is_available() else "cpu",
                disable_update=True, # 关闭funasr库的自动更新检查
                hub="hf"
                # chunk_size=96,
                # chunk_interval=10,
                # encoder_chunk_look_back=4,
                # decoder_chunk_look_back=2,
            )
        self.tmp_dir = config.get("tmp_dir", "")

    def save_audio_to_file(self, audio_data: List[bytes], session_id: str, file_path: str) -> str:
        """将音频数据保存到文件中"""
        file_name = f"{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.tmp_dir, file_name)
        with wave.open(file_path, "wb") as f:
            f.setnchannels(1) # 单声道 # TODO 硬编码
            f.setsampwidth(2) # 16位 # TODO 硬编码
            f.setframerate(16000) # 16kHz # TODO 硬编码
            f.writeframes(b''.join(audio_data))
        logger.debug(f"音频数据已保存到文件: {file_path}")
        return file_path

    def speech_to_text(self, audio_data: List[bytes], session_id: str) -> str:
        """将音频数据转换为文本"""
        start_time = time.time()
        file_path = self.save_audio_to_file(audio_data, session_id, self.tmp_dir)
        logger.debug(f"音频数据保存到：{file_path}，耗时: {time.time() - start_time} 秒")

        # 使用FunASR模型进行语音识别
        start_time = time.time()
        result = self.model.generate(
            input=b''.join(audio_data), 
            cache={}, 
            language="auto", # "auto", "zh", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True, # 输出结果中是否包含标点与逆文本正则化。
            batch_size_s=60 # 表示采用动态 batch，batch 中总音频时长，单位为秒 s。
        )
        # 使用 rich_transcription_postprocess 对结果进行后处理
        result = rich_transcription_postprocess(result[0]["text"]) 
        logger.debug(f"ASR结果：{result}，耗时: {time.time() - start_time} 秒")
        return result

# 通过工厂模式，实现根据查找表，动态实例化ASR（自动语音识别）类
class ASRClientFactory:
    # 类名-类对象 的查找表
    _cls_map = {
        "FunASR": FunASRClient,
    }

    @classmethod    
    def create(cls, name: str, *args, **kwargs) -> BaseASRClient:
        """根据配置创建ASR客户端实例"""
        client_class = cls._cls_map.get(name, None)
        if client_class is not None:
            logger.info(f"受支持的ASR类型: {name}")
            return client_class(*args, **kwargs)
        
        logger.critical(f"不支持的ASR类型: {name}")
        raise ValueError(f"不支持的ASR类型: {name}")
