import logging

def setup_logging():
    """配置日志系统"""
    # 创建一个格式器，定义日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建文件处理器
    file_handler = logging.FileHandler('app.log', 'a', encoding='utf-8') # 日志输出到文件，'a'为追加模式，'w'为覆盖写入
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG) # 设置日志级别（ DEBUG < INFO < WARNING < ERROR < CRITICAL ）

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 设置根记录器的级别为DEBUG
    
    # 清除所有已存在的处理器
    root_logger.handlers.clear()
    
    # 添加处理器到根记录器
    root_logger.addHandler(file_handler)
    # root_logger.addHandler(console_handler)