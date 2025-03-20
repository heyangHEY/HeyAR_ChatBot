import logging
from abc import ABC, abstractmethod
import torch
import numpy as np

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
    
class SileroVADClient(BaseVADClient):
    def __init__(self, config):
        self.config = config
        
        self.sample_rate: int = config.get("sample_rate", 16000)
        # 16kHz * 32ms = 512 samples
        # 8kHz * 32ms = 256 samples
        self.num_samples: int = 512 if self.sample_rate == 16000 else 256
        self.threshold: float = config.get("threshold", 0.5)
        self.min_speech_duration_ms: int = config.get("min_speech_duration_ms", 300)
        # 加载 Silero VAD 模型
        model_dir = config.get("model_dir", "snakers4/silero-vad")
        if model_dir == "snakers4/silero-vad":
            source = 'github'
        else:
            source = 'local'
        device = config.get("device", "cpu")
        
        # 加载 Silero VAD 模型
        model, utils = torch.hub.load(
            repo_or_dir=model_dir,  # 本地路径 或 GitHub仓库地址
            source=source,          # 'local' 本地路径，'github' GitHub仓库地址
            model='silero_vad',     # 模型名称（仓库中定义的入口函数名）
            force_reload=False      # 为True时，强制重新下载模型（即使本地已缓存），为False时，使用本地缓存
        )
        model.eval()
        if device != "cpu" and torch.cuda.is_available():
            model = model.to(device)
        self.vad = model
    
    def is_speech(self, frame) -> bool:
        try:
            # 将音频数据转换为适合模型的格式
            audio_tensor = torch.from_numpy(np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0)
            
            # 确保音频是单声道
            if len(audio_tensor.shape) > 1:
                audio_tensor = audio_tensor.mean(dim=0)
            
            # 检查音频长度是否满足要求
            assert len(audio_tensor) == self.num_samples, f"number of samples is not equal to {self.num_samples}"
            
            # 进行语音检测
            speech_prob = self.vad(audio_tensor, self.sample_rate).item()
            return bool(speech_prob > self.threshold)
            
        except Exception as e:
            logger.error(f"Error in Silero VAD speech detection: {str(e)}")
            return False
