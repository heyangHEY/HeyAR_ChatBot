import uvloop
import logging
import argparse
from core.utils.config import ConfigLoader
from core.utils.logger import setup_logging
from core.service import VoiceChatBotService

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)

async def main(config_file):
    # 设置日志系统
    setup_logging()
    
    logger.info("----------Voice Chat Bot Service started----------")

    # 读取yaml配置
    config = ConfigLoader(config_file)
    # 实例化语音助手服务
    service = VoiceChatBotService(
        config=config
    )
    # 初始化服务
    await service.init()
    # 启动服务

    # session_id
    # audio input
    # vad
    # asr
    # llm
    # tts
    # audio output
    
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yml', help='Path to config file')
    args = parser.parse_args()
    config_file = args.config

    uvloop.run(main(config_file))
