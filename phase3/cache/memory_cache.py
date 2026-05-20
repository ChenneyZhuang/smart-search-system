#!/usr/bin/env python3
"""
内存缓存模块 - 提供全局缓存功能
解决phase3.cache.memory_cache导入错误问题
"""

import time
import json
import hashlib
from typing import Dict, Any, Optional, Union
from threading import Lock
from dataclasses import dataclass

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: int  # 生存时间（秒）

class MemoryCache:
    """内存缓存"""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                # 检查是否过期
                if time.time() - entry.timestamp < entry.ttl:
                    self.hits += 1
                    return entry.data
                else:
                    # 过期，删除
                    del self.cache[key]
            
            self.misses += 1
            return None
    
    def set(self, key: str, data: Any, ttl: int = 3600) -> None:
        """设置缓存值"""
        with self.lock:
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl
            )
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "size": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "total_requests": total
            }

# 全局缓存实例
_global_cache: Optional[MemoryCache] = None

def get_global_cache() -> MemoryCache:
    """获取全局缓存实例（单例模式）"""
    global _global_cache
    if _global_cache is None:
        _global_cache = MemoryCache()
    return _global_cache

def create_cache_key(*args, **kwargs) -> str:
    """创建缓存键"""
    # 将参数序列化为字符串
    key_parts = []
    
    # 添加位置参数
    for arg in args:
        key_parts.append(str(arg))
    
    # 添加关键字参数（排序以确保一致性）
    for key in sorted(kwargs.keys()):
        key_parts.append(f"{key}:{kwargs[key]}")
    
    # 组合并哈希
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()

# 简化API
def cache_get(key: str) -> Optional[Any]:
    """获取缓存（简化API）"""
    return get_global_cache().get(key)

def cache_set(key: str, data: Any, ttl: int = 3600) -> None:
    """设置缓存（简化API）"""
    get_global_cache().set(key, data, ttl)

def cache_delete(key: str) -> bool:
    """删除缓存（简化API）"""
    return get_global_cache().delete(key)

def cache_clear() -> None:
    """清空缓存（简化API）"""
    get_global_cache().clear()

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计（简化API）"""
    return get_global_cache().get_stats()

if __name__ == "__main__":
    # 测试代码
    cache = get_global_cache()
    
    # 测试设置和获取
    cache.set("test_key", "test_value", ttl=10)
    value = cache.get("test_key")
    print(f"测试获取: {value}")
    
    # 测试统计
    stats = cache.get_stats()
    print(f"缓存统计: {stats}")
    
    # 测试键生成
    key = create_cache_key("search", "python爬虫", page=1)
    print(f"生成的缓存键: {key}")