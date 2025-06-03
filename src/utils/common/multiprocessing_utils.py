"""多进程工具模块"""
import multiprocessing
import os

def set_multiprocessing_start_method():
    """设置多进程启动方法为 spawn
    
    这个函数应该在程序最开始就调用，确保所有子进程都使用 spawn 方式启动
    """
    try:
        # 尝试设置启动方法
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        # 如果已经设置过，则忽略错误
        pass

# 在模块导入时就设置启动方法
set_multiprocessing_start_method() 