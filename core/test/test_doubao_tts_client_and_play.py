import yaml
import asyncio
from core.component.tts.doubao import AsyncDouBaoTTSClient
from core.component.audio.handler import AudioHandler

def load_tts_config():
    """从配置文件加载TTS配置"""
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["TTS"]["DouBaoTTS"]

def load_audio_config():
    """从配置文件加载音频配置"""
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["AUDIO"]["General"]

async def test_stream_tts():
    """测试流式文本转语音"""
    tts_config = load_tts_config()
    tts_client = AsyncDouBaoTTSClient(config=tts_config)

    audio_config = load_audio_config()
    audio_handler = AudioHandler(config=audio_config)
    await audio_handler.init()

    async def text_generator():
        texts = ["你好,", "这是一个", "流式合成测试。", 
                 "你好，这是一个豆包双向流式TTS的测试。",
                 "接下来是凑字数、凑时长，哈哈哈哈。"]
        for text in texts:
            yield text
            
    tts_generator = tts_client.astream_tts(text_generator())
    
    # 异步播放音频流
    chunks = bytearray()
    _size = audio_handler.output_config.frames_per_buffer * 2 # n frames * 2 bytes per sample
    
    try:
        async for chunk in tts_generator:
            if chunk is not None:
                chunks.extend(chunk)
                while len(chunks) >= _size:
                    audio_handler.ostream_buffer.put(bytes(chunks[:_size]))
                    chunks = chunks[_size:]
    
        if chunks:
            padding = b'\x00' * (_size - len(chunks))
            chunks.extend(padding)
            audio_handler.ostream_buffer.put(bytes(chunks))
    except Exception as e:
        print(f"异步播放音频流失败: {str(e)}")

    # 等待所有数据播放完成
    while not audio_handler.is_playback_complete():
        await asyncio.sleep(0.01)  # 每10ms检查一次播放状态

    if audio_handler:
        audio_handler.cleanup_resource()

if __name__ == "__main__":
    asyncio.run(test_stream_tts())
