#!/usr/bin/env python3
"""
增强内存缓存模块 - 智能TTL和热点检测
提供与memory_cache相同的接口，但具有增强功能
"""

import time
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from threading import Lock
from collections import defaultdict, deque
from dataclasses import dataclass
import statistics

@dataclass
class EnhancedCacheEntry:
    """增强缓存条目"""
    data: Any
    timestamp: float
    base_ttl: int  # 基础生存时间
    access_count: int = 0
    last_access_time: float = 0
    popularity_score: float = 0.0

class EnhancedMemoryCache:
    """增强内存缓存 - 智能TTL和热点检测"""
    
    def __init__(self):
        self.cache: Dict[str, EnhancedCacheEntry] = {}
        self.lock = Lock()
        
        # 统计信息
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        # 热点检测
        self.access_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.popular_items: List[Tuple[str, float]] = []
        self.last_popularity_update = time.time()
        
        # 智能TTL配置
        self.min_ttl = 300  # 5分钟
        self.max_ttl = 86400  # 24小时
        self.base_ttl = 3600  # 1小时
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，更新访问统计"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # 检查是否过期（使用动态TTL）
                dynamic_ttl = self._calculate_dynamic_ttl(entry)
                if time.time() - entry.timestamp < dynamic_ttl:
                    # 更新访问统计
                    entry.access_count += 1
                    entry.last_access_time = time.time()
                    
                    # 记录访问历史
                    self.access_history[key].append(time.time())
                    
                    self.hits += 1
                    return entry.data
                else:
                    # 过期，删除
                    del self.cache[key]
                    self.evictions += 1
            
            self.misses += 1
            return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值，使用智能TTL"""
        with self.lock:
            base_ttl = ttl if ttl is not None else self.base_ttl
            
            # 根据历史访问模式调整TTL
            if key in self.access_history:
                access_pattern = self._analyze_access_pattern(key)
                if access_pattern.get("is_hot", False):
                    # 热点项目，延长TTL
                    base_ttl = min(base_ttl * 2, self.max_ttl)
            
            self.cache[key] = EnhancedCacheEntry(
                data=data,
                timestamp=time.time(),
                base_ttl=base_ttl,
                last_access_time=time.time()
            )
    
    def _calculate_dynamic_ttl(self, entry: EnhancedCacheEntry) -> int:
        """计算动态TTL"""
        base_ttl = entry.base_ttl
        
        # 根据访问频率调整TTL
        if entry.access_count > 10:
            # 频繁访问的项目，延长TTL
            ttl_multiplier = min(1.0 + (entry.access_count / 100), 3.0)
            dynamic_ttl = int(base_ttl * ttl_multiplier)
        else:
            dynamic_ttl = base_ttl
        
        # 确保在合理范围内
        return max(self.min_ttl, min(dynamic_ttl, self.max_ttl))
    
    def _analyze_access_pattern(self, key: str) -> Dict[str, Any]:
        """分析访问模式"""
        history = self.access_history[key]
        if len(history) < 2:
            return {"is_hot": False, "access_rate": 0}
        
        # 计算访问频率（最近10次访问）
        recent_history = list(history)[-10:] if len(history) >= 10 else list(history)
        
        if len(recent_history) < 2:
            return {"is_hot": False, "access_rate": 0}
        
        # 计算平均访问间隔
        intervals = []
        for i in range(1, len(recent_history)):
            intervals.append(recent_history[i] - recent_history[i-1])
        
        avg_interval = statistics.mean(intervals) if intervals else 0
        
        # 判断是否为热点项目
        is_hot = avg_interval < 300  # 平均访问间隔小于5分钟
        
        return {
            "is_hot": is_hot,
            "access_rate": 1.0 / avg_interval if avg_interval > 0 else 0,
            "avg_interval": avg_interval,
            "access_count": len(history)
        }
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                if key in self.access_history:
                    del self.access_history[key]
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_history.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.popular_items.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            
            # 计算缓存大小和内存使用估计
            cache_size = len(self.cache)
            
            # 更新热点项目列表
            self._update_popular_items()
            
            return {
                "size": cache_size,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": hit_rate,
                "total_requests": total,
                "popular_items": self.popular_items[:5],  # 前5个热点项目
                "cache_type": "enhanced"
            }
    
    def _update_popular_items(self):
        """更新热点项目列表"""
        current_time = time.time()
        # 每5分钟更新一次
        if current_time - self.last_popularity_update < 300:
            return
        
        popularity_scores = []
        for key, entry in self.cache.items():
            # 计算流行度分数（基于访问频率和新鲜度）
            recency = current_time - entry.last_access_time
            recency_score = 1.0 / (recency + 1)  # 避免除零
            
            access_frequency = entry.access_count / (current_time - entry.timestamp + 1)
            
            popularity = recency_score * 0.3 + access_frequency * 0.7
            popularity_scores.append((key, popularity))
        
        # 按流行度排序
        popularity_scores.sort(key=lambda x: x[1], reverse=True)
        self.popular_items = popularity_scores[:10]  # 前10个热点项目
        
        self.last_popularity_update = current_time
    
    def optimize(self):
        """优化缓存 - 清理过期项目和低价值项目"""
        with self.lock:
            current_time = time.time()
            keys_to_delete = []
            
            for key, entry in self.cache.items():
                dynamic_ttl = self._calculate_dynamic_ttl(entry)
                
                # 检查是否过期
                if current_time - entry.timestamp > dynamic_ttl:
                    keys_to_delete.append(key)
                    continue
                
                # 检查是否为低价值项目（长时间未访问）
                if entry.access_count == 0 and current_time - entry.timestamp > self.base_ttl * 2:
                    keys_to_delete.append(key)
            
            # 删除过期/低价值项目
            for key in keys_to_delete:
                del self.cache[key]
                self.evictions += 1
            
            return len(keys_to_delete)

# 全局增强缓存实例
_global_enhanced_cache: Optional[EnhancedMemoryCache] = None

def get_global_cache() -> EnhancedMemoryCache:
    """获取全局增强缓存实例（单例模式）"""
    global _global_enhanced_cache
    if _global_enhanced_cache is None:
        _global_enhanced_cache = EnhancedMemoryCache()
    return _global_enhanced_cache

# 保持与memory_cache相同的API
def create_cache_key(*args, **kwargs) -> str:
    """创建缓存键"""
    key_parts = []
    
    for arg in args:
        key_parts.append(str(arg))
    
    for key in sorted(kwargs.keys()):
        key_parts.append(f"{key}:{kwargs[key]}")
    
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()

# 简化API
def cache_get(key: str) -> Optional[Any]:
    """获取缓存（简化API）"""
    return get_global_cache().get(key)

def cache_set(key: str, data: Any, ttl: Optional[int] = None) -> None:
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

def optimize_cache() -> int:
    """优化缓存（清理过期项目）"""
    return get_global_cache().optimize()

if __name__ == "__main__":
    # 测试增强缓存
    cache = get_global_cache()
    
    print("🧪 测试增强缓存功能...")
    
    # 测试设置和获取
    cache.set("test1", "value1", ttl=10)
    cache.set("test2", "value2", ttl=20)
    
    # 模拟多次访问test1（使其成为热点）
    for i in range(5):
        cache.get("test1")
        time.sleep(0.1)
    
    value1 = cache.get("test1")
    value2 = cache.get("test2")
    print(f"测试获取 test1: {value1}")
    print(f"测试获取 test2: {value2}")
    
    # 获取统计信息
    stats = cache.get_stats()
    print(f"增强缓存统计: {json.dumps(stats, indent=2)}")
    
    # 测试优化
    optimized = cache.optimize()
    print(f"优化缓存，清理了 {optimized} 个项目")
    
    print("✅ 增强缓存测试完成")