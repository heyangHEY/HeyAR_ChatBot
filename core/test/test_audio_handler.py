import asyncio
import logging
import argparse
from core.utils.config import ConfigLoader
from core.component.audio import AudioIOHandler

logging.basicConfig(
    level=logging.DEBUG, # 设置日志级别（ DEBUG < INFO < WARNING < ERROR < CRITICAL ）
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename="app.log", # 日志输出到文件
    filemode='a' # 'a'为追加模式，'w'为覆盖写入
)
logger = logging.getLogger(__name__) # 获取日志记录器实例，使用模块名命名

async def test_audio_io_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yml', help='Path to config file')
    args = parser.parse_args()
    config_file = args.config
    # 读取yaml配置
    all_config = ConfigLoader(config_file)
    audio_config = all_config.get_audio_config()
    handler = AudioIOHandler(audio_config)
    await handler.init()
    await handler.test("recording.wav", 5)

if __name__ == "__main__":
    asyncio.run(test_audio_io_handler())
