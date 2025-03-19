import os
import yaml
import pytest
from core.component.tts.doubao import AsyncDouBaoTTSClient

def load_config():
    """从配置文件加载TTS配置"""
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["TTS"]["DouBaoTTS"]

@pytest.mark.asyncio
async def test_tts_to_file():
    """测试文本转语音到文件"""
    config = load_config()
    client = AsyncDouBaoTTSClient(config=config)
    
    text = "你好,这是一个测试。"
    output_path = "tmp/tts/test.mp3"
    
    await client.tts_to_file(text, output_path)
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0

@pytest.mark.asyncio 
async def test_stream_tts():
    """测试流式文本转语音"""
    config = load_config()
    client = AsyncDouBaoTTSClient(config=config)

    async def text_generator():
        texts = ["你好,", "这是一个", "流式合成测试。"]
        for text in texts:
            yield text
            
    output_path = "tmp/tts/test_stream.mp3"

    await client.astream_tts_to_file(text_generator(), output_path)    
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0

if __name__ == "__main__":
    pytest.main()
