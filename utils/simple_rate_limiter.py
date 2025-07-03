"""限流控制器: 根据在线 API 的限流规则进行设置"""

import time
import threading
from config.global_config import GlobalConfig
from utils.log_utils import logger


class SimpleRateLimiter:
    """简单的限流控制器"""

    def __init__(self, model_name: str = None):
        self.config = GlobalConfig.get_llm_config(model_name)
        self.qpm = self.config["qpm"]  # 每分钟最大请求数
        self.last_request_time = 0  # 上次请求时间
        self.request_count = 0  # 当前分钟内的请求数
        self.minute_start = time.time()  # 当前分钟开始时间
        self.lock = threading.Lock()

        logger.info(f"初始化限流器 - QPM: {self.qpm}")

    def wait_if_needed(self):
        """如果需要，等待直到可以发送请求"""
        with self.lock:
            current_time = time.time()

            # 检查是否需要重置计数器（新的一分钟）
            if current_time - self.minute_start >= 60:
                self.request_count = 0
                self.minute_start = current_time

            # 检查是否超过QPM限制
            if self.request_count >= self.qpm:
                # 计算需要等待的时间
                wait_time = 60 - (current_time - self.minute_start)
                if wait_time > 0:
                    logger.info(f"API限流，等待 {wait_time:.1f} 秒...")
                    time.sleep(wait_time)
                    return self.wait_if_needed()  # 递归检查

            # 记录请求
            self.last_request_time = current_time
            self.request_count += 1


# 全局限流器实例
rate_limiter = SimpleRateLimiter(GlobalConfig.LLM_NAME)
