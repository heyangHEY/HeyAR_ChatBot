import os
import logging
import logging.config

def setup_logging(config: dict) -> None:
    """初始化日志配置
    
    Args:
        config: 日志配置字典
    """
    # 获取日志配置
    log_path = config.get('path', None)
    log_level = config.get('level', 'INFO')
    log_on_console = config.get('on_console', True)
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': {},
        'root': {
            'handlers': [],
            'level': log_level,  # 根记录器默认级别设为DEBUG
        },
    }
    
    # 如果指定了日志文件路径，添加文件处理器
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        config['handlers']['file'] = {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': log_path,
            'mode': 'a',
        }
        config['root']['handlers'].append('file')
    
    # 如果配置了在控制台输出日志，添加控制台处理器
    if log_on_console:
        config['handlers']['console'] = {
            'level': log_level,
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        }
        config['root']['handlers'].append('console')
    
    # 应用配置
    logging.config.dictConfig(config)

def set_log_level(level: str) -> None:
    """设置根日志记录器的日志级别
    
    Args:
        level: 日志级别，可以是 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' 的其中之一
    """
    # 转换日志级别字符串为对应的数值
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'无效的日志级别: {level}')
    
    # 设置根日志记录器的级别
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 更新所有处理器的级别
    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)  # 所有处理器使用相同的级别

    logging.info(f"日志级别已设置为: {level}")
