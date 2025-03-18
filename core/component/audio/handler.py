import os
import logging
import pyaudio
import queue
import wave
from typing import Optional, Dict, Any, List
import numpy as np
from core.utils.redirect import suppress_stderr
import asyncio
from scipy.signal import resample_poly
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 音频配置常量
AUDIO_FORMAT = pyaudio.paInt16
BYTES_PER_SAMPLE = 2  # paInt16 = 2 bytes
DEFAULT_CHANNELS = 1
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_DURATION_MS = 10

@dataclass
class AudioConfig:
    """音频配置数据类"""
    channels: int
    sample_rate: int
    chunk_duration_ms: int
    device_name: str = ""

    @property
    def frames_per_buffer(self) -> int:
        """计算每个缓冲区的帧数"""
        return int(self.sample_rate / 1000 * self.chunk_duration_ms) # 比如 16kHz * 30ms = 480 frames

class AudioHandler:
    """异步的音频输入输出处理类
    
    处理音频设备的输入（麦克风）和输出（扬声器）流。
    支持实时音频采集和播放，以及采样率转换。
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 包含输入输出配置的字典
                   格式: {"input": {...}, "output": {...}}
        """
        with suppress_stderr(): # 抑制pyaudio的警告
            self.pa = pyaudio.PyAudio()
        
        # 初始化输入输出配置
        self.input_config = AudioConfig(
            channels=config.get("input", {}).get("channels", DEFAULT_CHANNELS),
            sample_rate=config.get("input", {}).get("sample_rate", DEFAULT_SAMPLE_RATE),
            chunk_duration_ms=config.get("input", {}).get("chunk_duration", DEFAULT_CHUNK_DURATION_MS),
            device_name=config.get("input", {}).get("name", "")
        )
        
        self.output_config = AudioConfig(
            channels=config.get("output", {}).get("channels", DEFAULT_CHANNELS),
            sample_rate=config.get("output", {}).get("sample_rate", DEFAULT_SAMPLE_RATE),
            chunk_duration_ms=config.get("output", {}).get("chunk_duration", DEFAULT_CHUNK_DURATION_MS),
            device_name=config.get("output", {}).get("name", "")
        )

        # 初始化流和缓冲区
        self.istream: Optional[pyaudio.Stream] = None
        self.ostream: Optional[pyaudio.Stream] = None
        self.istream_buffer: queue.Queue = queue.Queue()
        self.ostream_buffer: queue.Queue = queue.Queue()
        self.istream_active: bool = True # 控制回调函数中的行为，为True时，拾音并写入buffer；为False时，屏蔽麦克风输入。
        self.ostream_active: bool = True # 控制回调函数中的行为，为True时，播放buffer中的数据；为False时，静默。

        self.tmp_dir = config.get("tmp_dir", "")

    async def init(self) -> None:
        """初始化音频设备和流"""
        try:
            self._enumerate_device()
            self._open_streams()
            self._start_streams()
            # ! 测试发现，istream.start_stream()后尚需一段时间，才开始拾音。可以在回调函数中，当首次收到音频数据时触发设备就绪事件。
            # ! 此处简单异步延迟2s。
            await asyncio.sleep(2)  # 等待设备就绪
        except Exception as e:
            self._cleanup_resource()
            raise RuntimeError(f"初始化音频处理器失败: {str(e)}") from e

    def _enumerate_device(self) -> None:
        """枚举并记录所有可用的音频设备"""
        dev_count = self.pa.get_device_count()
        logger.debug(f"发现 {dev_count} 个音频设备")

        for i in range(dev_count):
            dev_info = self.pa.get_device_info_by_index(i)
            logger.debug(
                f"索引: {dev_info['index']}, "
                f"名称: {dev_info['name']}, "
                f"采样率: {dev_info['defaultSampleRate']} Hz, "
                f"输入通道: {dev_info['maxInputChannels']}, "
                f"输出通道: {dev_info['maxOutputChannels']}"
            )

    def _find_device(self, is_input: bool) -> int:
        """查找指定的输入或输出设备
        
        Args:
            is_input: True表示查找输入设备，False表示查找输出设备
            
        Returns:
            找到的设备索引
            
        Raises:
            RuntimeError: 未找到合适的设备
        """
        dev_name = self.input_config.device_name if is_input else self.output_config.device_name
        device_type = "输入" if is_input else "输出"
        
        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            channels_key = "maxInputChannels" if is_input else "maxOutputChannels"
            
            if dev_info[channels_key] > 0 and dev_name in dev_info["name"]:
                logger.info(f"找到目标{device_type}设备 {i}: {dev_info['name']}")
                return i
        
        raise RuntimeError(f"未找到合适的{device_type}设备，名称: {dev_name}")

    # pyaudio.paContinue, 通知音频流继续运行，回调函数会持续被调用。
    # pyaudio.paComplete, 通知音频流停止运行，回调函数不再被调用。
    # queue.put(item) = put(item, block=True, timeout=None), 添加元素，队列满时阻塞
    # queue.put_nowait() = put(block=False), 添加元素，队列满时抛出异常 queue.Full
    # queue.get() = queue.get(block=True, timeout=None), 取出元素，队列空时阻塞
    # queue.get_nowait() = get(block=False), 取出元素，队列空时抛出异常 queue.Empty
    def _istream_callback(self, in_data: bytes, frame_count: int, time_info: Dict, status: int) -> tuple:
        """音频输入回调函数"""
        # TODO 当首次收到音频数据时触发设备就绪事件
        # TODO check 是否有 queue.Full 异常？
        if self.istream_active:
            self.istream_buffer.put(in_data)
        return None, pyaudio.paContinue

    # 1. ostream未激活时，输出静音
    # 2. 激活，但输出队列为空时，输出静音
    # 3. 激活，且输出队列非空时，取出元素并输出
    def _ostream_callback(self, in_data: bytes, frame_count: int, time_info: Dict, status: int) -> tuple:
        """音频输出回调函数"""
        try:
            if self.ostream_active:
                data = self.ostream_buffer.get_nowait()
            else:
                # bytes_per_frame = self.channels * pyaudio.get_sample_size(pyaudio.paInt16)
                # 单通道16位，bytes_per_frame = 1 * 2 = 2 字节
                data = b'\x00' * frame_count * BYTES_PER_SAMPLE # 静音
        except queue.Empty:
            data = b'\x00' * frame_count * BYTES_PER_SAMPLE # 静音
        return data, pyaudio.paContinue

    def _start_streams(self):
        if self.istream is not None:
            self.istream.start_stream()
        if self.ostream is not None:
            self.ostream.start_stream()

    def _open_streams(self):
        in_channels = self.input_config.channels
        in_sample_rate = self.input_config.sample_rate
        in_chunk_duration_ms = self.input_config.chunk_duration_ms
        in_frames_per_buffer = self.input_config.frames_per_buffer

        out_channels = self.output_config.channels
        out_sample_rate = self.output_config.sample_rate
        out_chunk_duration_ms = self.output_config.chunk_duration_ms
        out_frames_per_buffer = self.output_config.frames_per_buffer

        try:
            self.istream = self.pa.open(
                format = AUDIO_FORMAT,
                channels = in_channels,
                rate = in_sample_rate,
                input = True,
                frames_per_buffer = in_frames_per_buffer,
                stream_callback = self._istream_callback,
                input_device_index = self._find_device(True),
                start = False # 先不启动流，等整个系统的所有组件都准备好之后再手动开启流，避免消费者尚未到位时，就开始生产
            )
            logger.info(
                f"成功打开输入流, "
                f"channels: {in_channels}, "
                f"rate: {in_sample_rate}, "
                f"frames_per_buffer: {in_frames_per_buffer}"
            )
        except Exception as e:
            self._cleanup_resource()
            raise RuntimeError(f"无法打开输入流：{str(e)}") from e
        
        try:
            self.ostream = self.pa.open(
                format = AUDIO_FORMAT,
                channels = out_channels,
                rate = out_sample_rate,
                output = True,
                frames_per_buffer = out_frames_per_buffer,
                stream_callback = self._ostream_callback,
                output_device_index = self._find_device(False),
                start = False
            )
            logger.info(
                f"成功打开输出流, "
                f"channels: {out_channels}, "
                f"rate: {out_sample_rate}, "
                f"frames_per_buffer: {out_frames_per_buffer}"
            )
        except Exception as e:
            self._cleanup_resource()
            raise RuntimeError(f"无法打开输出流：{str(e)}") from e

    def _cleanup_resource(self) -> None:
        """清理所有已分配的音频资源"""
        try:
            if self.istream is not None:
                if not self.istream.is_stopped():
                    self.istream.stop_stream()
                self.istream.close()
            if self.ostream is not None:
                if not self.ostream.is_stopped():
                    self.ostream.stop_stream()
                self.ostream.close()
            self.pa.terminate()
        except Exception as e:
            logger.error(f"清理音频资源时发生错误: {str(e)}")

    async def test(self, temp_file: str, seconds: int) -> None:
        """测试音频录制和播放功能
        
        Args:
            temp_file: 临时音频文件的路径
            seconds: 录音时长（秒）
        """
        try:
            temp_file = os.path.join(self.tmp_dir, temp_file)
            self._test_record_audio(seconds, temp_file)
            await self._test_play_audio(temp_file)
        except Exception as e:
            logger.error(f"音频测试失败: {str(e)}")
            raise

    def _test_record_audio(self, duration_s: int, temp_file: str) -> None:
        """测试音频录制功能
        
        Args:
            duration_s: 录音时长（秒）
            temp_file: 保存录音的文件路径
        """
        try:
            frames: List[bytes] = []
            self.istream_buffer = queue.Queue()  # 清空buffer中的历史数据
            
            # 计算需要采集的音频片段数量
            count = int(duration_s * 1000 / self.input_config.chunk_duration_ms)
            logger.debug(f"开始录音，时长：{duration_s} 秒")
            
            # 采集音频数据
            for _ in range(count):
                frame = self.istream_buffer.get()
                # 如果输入输出采样率不同，进行重采样
                if self.output_config.sample_rate != self.input_config.sample_rate:
                    frame = self._resample(
                        frame, 
                        self.input_config.sample_rate,
                        self.output_config.sample_rate
                    )
                frames.append(frame)
            logger.debug("录音完成")

            # 保存音频文件
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(self.input_config.channels)
                wf.setsampwidth(BYTES_PER_SAMPLE)
                wf.setframerate(self.output_config.sample_rate) # 填写重采样后的采样率
                wf.writeframes(b''.join(frames))
            logger.debug(f"录音已保存：{temp_file}")
        except Exception as e:
            logger.error(f"录音失败: {str(e)}")
            raise

    async def _test_play_audio(self, temp_file: str) -> None:
        """测试音频播放功能
        
        Args:
            temp_file: 要播放的音频文件路径
        """
        try:
            with wave.open(temp_file, 'rb') as wf:
                frames_per_buffer = self.output_config.frames_per_buffer
                data = wf.readframes(frames_per_buffer)
                while data:
                    self.ostream_buffer.put(data)
                    data = wf.readframes(frames_per_buffer)
            
            # 等待所有数据播放完成
            while not self._is_playback_complete():
                await asyncio.sleep(0.05)  # 每50ms检查一次播放状态
            
            logger.debug(f"播放完成：{temp_file}")
        except Exception as e:
            logger.error(f"播放失败: {str(e)}")
            raise

    def _is_playback_complete(self) -> bool:
        """检查音频播放是否完成
        
        Returns:
            如果输出缓冲区为空且输出流处于活动状态，返回True
        """
        return (self.ostream_buffer.empty() and 
                self.ostream is not None and 
                self.ostream.is_active())

    def _resample(self, data: bytes, in_sample_rate: int, out_sample_rate: int) -> bytes:
        """对音频数据进行重采样
        
        Args:
            data: 原始音频数据
            in_sample_rate: 输入采样率
            out_sample_rate: 输出采样率
            
        Returns:
            重采样后的音频数据
        """
        try:
            # 将字节数据转换为numpy数组
            samples = np.frombuffer(data, dtype=np.int16)
            # 使用多相滤波进行重采样
            resampled = resample_poly(samples, out_sample_rate, in_sample_rate) # 24k/16k=24/16=3/2
            # 转换回int16类型的字节数据
            return resampled.astype(np.int16).tobytes()
        except Exception as e:
            logger.error(f"重采样失败: {str(e)}")
            raise
