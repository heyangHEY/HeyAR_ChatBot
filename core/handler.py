import uvloop
import logging
import argparse
from core.config import ConfigLoader
from core.service import VoiceChatBotService

logging.basicConfig(
    level=logging.INFO, # 设置日志级别（DEBUG < INFO < WARNING < ERROR < CRITICAL）
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename="app.log", # 日志输出到文件
    filemode='a' # 'a'为追加模式，'w'为覆盖写入
)
logger = logging.getLogger(__name__) # 获取日志记录器实例，使用模块名命名

async def main(config_file):
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
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yml', help='Path to config file')
    args = parser.parse_args()
    config_file = args.config

    uvloop.run(main(config_file))
