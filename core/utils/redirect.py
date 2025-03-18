import os
import sys
import logging
from contextlib import contextmanager
from typing import Optional
from io import StringIO

@contextmanager
def suppress_stderr():
    """
    临时重定向stderr到os.devnull

    用于抑制不必要的错误输出，比如ALSA lib的警告信息
    """
    original_stderr_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    try:
        yield
    finally:
        # 恢复原始 stderr
        os.dup2(original_stderr_fd, 2)
        os.close(original_stderr_fd)
        os.close(devnull)

@contextmanager
def suppress_stdout():
    """
    临时重定向stdout到os.devnull

    用于抑制不必要的标准输出，比如FunASR的debug信息
    """
    original_stdout_fd = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    try:
        yield
    finally:
        # 恢复原始 stdout
        os.dup2(original_stdout_fd, 1)
        os.close(original_stdout_fd)
        os.close(devnull)

@contextmanager
def redirect_to_logger_low_level(logger: Optional[logging.Logger] = None):
    """
    使用底层文件描述符重定向将stdout和stderr重定向到logger的上下文管理器
    
    这个版本可以捕获C库等底层的输出，适合临时使用的场景
    
    Args:
        logger: 用于输出的logger实例。如果为None，则使用root logger
    
    Example:
        >>> with redirect_to_logger_low_level(logger):
        >>>     # 所有输出（包括底层库的输出）都会被重定向到logger
        >>>     print("这条消息会通过logger.info输出")
        >>>     print("错误消息", file=sys.stderr)  # 这条消息会通过logger.error输出
    """
    if logger is None:
        logger = logging.getLogger()

    # 保存原始的文件描述符
    old_stdout_fd = os.dup(1)
    old_stderr_fd = os.dup(2)

    # 创建管道（使用非阻塞模式）
    stdout_r, stdout_w = os.pipe()
    stderr_r, stderr_w = os.pipe()

    try:
        # 重定向标准输出和错误输出到管道
        os.dup2(stdout_w, 1)
        os.dup2(stderr_w, 2)
        
        # 立即关闭写入端
        os.close(stdout_w)
        os.close(stderr_w)

        yield

        # 恢复原始的文件描述符
        os.dup2(old_stdout_fd, 1)
        os.dup2(old_stderr_fd, 2)

        # 读取并记录输出
        for reader, level in [(os.fdopen(stdout_r, 'r'), logger.info),
                             (os.fdopen(stderr_r, 'r'), logger.error)]:
            with reader:
                while True:
                    line = reader.readline()
                    if not line:
                        break
                    line = line.rstrip('\n')
                    if line:
                        level(line)

    finally:
        # 关闭所有剩余的文件描述符
        os.close(old_stdout_fd)
        os.close(old_stderr_fd)
    