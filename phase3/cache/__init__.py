#!/usr/bin/env python3
"""
缓存模块包
提供内存缓存和增强缓存功能
"""

from .memory_cache import (
    MemoryCache,
    get_global_cache as get_memory_cache,
    create_cache_key,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    get_cache_stats
)

from .enhanced_memory_cache import (
    EnhancedMemoryCache,
    get_global_cache as get_enhanced_cache,
    optimize_cache
)

# 默认导出增强缓存
get_global_cache = get_enhanced_cache

__all__ = [
    # 基础缓存
    'MemoryCache',
    'get_memory_cache',
    'create_cache_key',
    'cache_get',
    'cache_set',
    'cache_delete',
    'cache_clear',
    'get_cache_stats',
    
    # 增强缓存
    'EnhancedMemoryCache',
    'get_enhanced_cache',
    'get_global_cache',  # 默认增强缓存
    'optimize_cache'
]

__version__ = "1.0.0"
__author__ = "Chenney's AI Assistant"