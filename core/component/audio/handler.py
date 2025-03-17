import logging
import pyaudio
import queue
import numpy as np
from .utils import suppress_stderr
import time
import asyncio
from scipy.signal import resample_poly # 音频数据的采样率转换（比如16kHz → 24kHz）

logger = logging.getLogger(__name__)

# 异步的音频InputStream、OutputStream处理类
class AudioIOHandler:
    def __init__(self, config: dict):
        with suppress_stderr(): # ALSA lib会报一些异常和错误到命令行，但不影响该服务，因此忽略之
            self.pa = pyaudio.PyAudio()
        self.icfg = config.get("input", {})
        self.ocfg = config.get("output", {})

        self.istream = None
        self.istream_buffer = queue.Queue()
        self.istream_active = True # 控制回调函数中的行为，为True时，拾音并写入buffer；为False时，屏蔽麦克风输入。

        self.ostream = None
        self.ostream_buffer = queue.Queue()
        self.ostream_active = True # 控制回调函数中的行为，为True时，读取buffer并播放；为False时，扬声器静音。

    async def init(self):
        self._enumerate_device()
        self._open_streams()
        self._start_streams()
        # ! 测试发现，istream.start_stream()后尚需一段时间，才开始拾音。可以在回调函数中，当首次收到音频数据时触发设备就绪事件。
        # ! 此处简单异步延迟2s。
        await asyncio.sleep(2)

    def _start_streams(self):
        if self.istream is not None:
            self.istream.start_stream()
        if self.ostream is not None:
            self.ostream.start_stream()

    def _enumerate_device(self):
        dev_count = self.pa.get_device_count()
        logger.debug(f"found {dev_count} audio device")

        for i in range(dev_count):
            dev_info = self.pa.get_device_info_by_index(i)
            logger.debug(
                f"index: {dev_info['index']}, "
                f"name: {dev_info['name']}, "
                f"采样率: {dev_info['defaultSampleRate']} Hz, "
                f"输入通道: {dev_info['maxInputChannels']}, "
                f"输出通道: {dev_info['maxOutputChannels']}"
            )

    def _find_input_device(self) -> int:
        dev_name = self.icfg.get("name", "")

        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            if dev_info["maxInputChannels"] > 0 and dev_name in dev_info["name"]:
                logger.info(f"found target audio input device {i}: {dev_info['name']}")
                return i
        
        logger.error("No suitable audio input device found, name: {dev_name}")
        raise RuntimeError("No suitable audio input device found")

    def _find_output_device(self) -> int:
        dev_name = self.ocfg.get("name", "")

        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            if dev_info["maxOutputChannels"] > 0 and dev_name in dev_info["name"]:
                logger.info(f"found target audio output device {i}: {dev_info['name']}")
                return i
        
        logger.error("No suitable audio output device found, name: {dev_name}")
        raise RuntimeError("No suitable audio output device found")
    
    # pyaudio.paContinue, 通知音频流继续运行，回调函数会持续被调用。
    # pyaudio.paComplete, 通知音频流停止运行，回调函数不再被调用。
    # queue.put(item) = put(item, block=True, timeout=None), 添加元素，队列满时阻塞
    # queue.put_nowait() = put(block=False), 添加元素，队列满时抛出异常 queue.Full
    # queue.get() = queue.get(block=True, timeout=None), 取出元素，队列空时阻塞
    # queue.get_nowait() = get(block=False), 取出元素，队列空时抛出异常 queue.Empty
    def _istream_callback(self, in_data, frame_count, time_info, status):
        """音频采集回调（在音频线程中运行）"""
        # TODO 当首次收到音频数据时触发设备就绪事件
        # TODO check 是否有 queue.Full 异常？
        if self.istream_active:
            self.istream_buffer.put(in_data) 
        return (None, pyaudio.paContinue)

    def _ostream_callback(self, in_data, frame_count, time_info, status):
        # 1. ostream未激活时，输出静音
        # 2. 激活，但输出队列为空时，输出静音
        # 3. 激活，且输出队列非空时，取出元素并输出
        try:
            if self.ostream_active:
                data = self.ostream_buffer.get_nowait()
            else:
                # bytes_per_frame = self.channels * pyaudio.get_sample_size(pyaudio.paInt16)
                # 单通道16位，bytes_per_frame = 1 * 2 = 2 字节
                data = b'\x00' * frame_count * 2 # 静音
        except queue.Empty:
            data = b'\x00' * frame_count * 2 # 静音
        return (data, pyaudio.paContinue)

    def _open_streams(self):
        in_channels = self.icfg.get("channels", 1)
        in_sample_rate = self.icfg.get("sample_rate", 16000)
        in_chunk_duration_ms = self.icfg.get("chunk_duration", 10) # ms，音频片段的时长
        in_frames_per_buffer = int(in_sample_rate / 1000 * in_chunk_duration_ms) # 16kHz * 30ms = 480 frames

        out_channels = self.ocfg.get("channels", 1)
        out_sample_rate = self.ocfg.get("sample_rate", 16000)
        out_chunk_duration_ms = self.ocfg.get("chunk_duration", 10) # ms，音频片段的时长
        out_frames_per_buffer = int(out_sample_rate / 1000 * out_chunk_duration_ms) # 24kHz * 30ms = 720 frames

        try:
            self.istream = self.pa.open(
                format = pyaudio.paInt16, # 2个字节
                channels = in_channels,
                rate = in_sample_rate,
                input = True,
                frames_per_buffer = in_frames_per_buffer,
                stream_callback = self._istream_callback,
                input_device_index = self._find_input_device(),
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
                format = pyaudio.paInt16,
                channels = out_channels,
                rate = out_sample_rate,
                output = True,
                frames_per_buffer = out_frames_per_buffer,
                stream_callback = self._ostream_callback,
                output_device_index = self._find_output_device(),
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

    def _cleanup_resource(self):
        """清理已分配的资源"""
        if self.istream is not None:
            if not self.istream.is_stopped():
                self.istream.stop_stream()
            self.istream.close()
        if self.ostream is not None:
            if not self.ostream.is_stopped():
                self.ostream.stop_stream()
            self.ostream.close()
        self.pa.terminate()

    # .test("./temp/recording.wav", 5)
    def test(self, temp_file: str, seconds: int):
        self._test_record_audio(seconds, temp_file)
        self._test_play_audio(temp_file)

    def _test_record_audio(self, duration_s: int, temp_file: str):
        in_channels = self.icfg.get("channels", 1)
        in_sample_rate = self.icfg.get("sample_rate", 16000)
        in_chunk_duration_ms = self.icfg.get("chunk_duration", 10) # ms，音频片段的时长

        out_sample_rate = self.ocfg.get("sample_rate", 16000)

        try:
            frames = []
            self.istream_buffer = queue.Queue() # ! 清空buffer中的历史数据
            count = int(duration_s * 1000 / in_chunk_duration_ms)
            logger.debug(f"开始录音，时长：{duration_s} s")
            for i in range(count):
                frame = self.istream_buffer.get()
                # 如果istream和ostream的采样率不一样，为了正常播放音频，在此处进行重采样
                if out_sample_rate != in_sample_rate:
                    frame = self._resample(frame, in_sample_rate, out_sample_rate)
                frames.append(frame)
            logger.debug(f"录音完成")

            import wave
            # 保存临时录音文件
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(in_channels)
                wf.setsampwidth(2) # self.pa.get_sample_size(pyaudio.paInt16)
                wf.setframerate(out_sample_rate) # 重采样后，新的字节流按照ostream的采样率
                wf.writeframes(b''.join(frames))
            logger.debug(f"录音已保存：{temp_file}")
        except Exception as e:
            logger.error(f"录音失败，{str(e)}")

    def _test_play_audio(self, temp_file: str):
        out_sample_rate = self.ocfg.get("sample_rate", 16000)
        out_chunk_duration_ms = self.ocfg.get("chunk_duration", 10) # ms，音频片段的时长
        out_frames_per_buffer = int(out_sample_rate / 1000 * out_chunk_duration_ms) # 24kHz * 30ms = 720 frames

        try:
            import wave
            if self.ostream is not None:
                self.ostream.start_stream()
            with wave.open(temp_file, 'rb') as wf:
                data = wf.readframes(out_frames_per_buffer)
                while data:
                    self.ostream_buffer.put(data)
                    data = wf.readframes(out_frames_per_buffer)
            time.sleep(5)
            logger.debug(f"播放完成：{temp_file}")
        except Exception as e:
            logger.error(f"播放失败，{str(e)}")

    # 采样率转换（16kHz → 24kHz）
    def _resample(self, data: bytes, in_sample_rate: int, out_sample_rate: int) -> bytes:
        # 将字节数据转换为numpy数组
        samples = np.frombuffer(data, dtype=np.int16)
        # 重采样（使用多相滤波）
        resampled = resample_poly(samples, out_sample_rate, in_sample_rate)  # 24k/16k=24/16=3/2
        # 转换为int16并返回字节
        return resampled.astype(np.int16).tobytes()
