# agent/utils/key_rotator.py
# -*- coding: utf-8 -*-
import os
from itertools import cycle

class ApiKeyManager:
    def __init__(self):
        self._keys = self._load_keys()
        if not self._keys:
            self._key_cycler = None
        else:
            self._key_cycler = cycle(self._keys)

    def _load_keys(self):
        """从环境变量加载以逗号分隔的API密钥"""
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        if not keys_str:
            # 兼容旧的单个key
            single_key = os.getenv("GEMINI_API_KEY")
            return [single_key] if single_key else []

        # 去除空格和空字符串
        return [key.strip() for key in keys_str.split(',') if key.strip()]

    def get_next_key(self):
        """获取下一个可用的API Key"""
        if not self._key_cycler:
            return None
        return next(self._key_cycler)

# 创建一个全局实例，以便所有模块共享同一个轮询状态
gemini_key_rotator = ApiKeyManager()

def get_next_gemini_key():
    """方便调用的函数"""
    return gemini_key_rotator.get_next_key()
