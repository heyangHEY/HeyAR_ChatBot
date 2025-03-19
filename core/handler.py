import uvloop
import logging
import argparse
from core.utils.config import ConfigLoader
from core.utils.logger import setup_logging
from core.service import VoiceChatBotService

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)

async def main(config_file):
    # 读取yaml配置
    config = ConfigLoader(config_file)
    # 设置日志系统
    log_cfg = config.get_log_config()
    setup_logging(log_cfg)

    logger.info("----------Voice Chat Bot Service started----------")
    version = config.get_all_config().get('version', "")
    logger.info(f'load config file, version: {version}, path: {config_file}')

    # 实例化语音助手服务
    service = VoiceChatBotService(
        config=config
    )
    # 初始化服务
    await service.init()
    # 启动服务
    await service.pipeline()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yml', help='Path to config file')
    args = parser.parse_args()
    config_file = args.config

    uvloop.run(main(config_file))
