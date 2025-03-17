import os
import sys
from contextlib import redirect_stdout, redirect_stderr, contextmanager

# 定义重定向上下文管理器
# with redirect_stdout(open(os.devnull, 'w')), redirect_stderr(open(os.devnull, 'w')):

@contextmanager
def suppress_stderr():
    # 备份并重定向 stderr
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
