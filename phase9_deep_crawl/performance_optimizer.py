#!/usr/bin/env python3
"""
性能优化器 - 优化爬取系统性能
包括连接池管理、缓存策略、内存优化、性能分析
"""

import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    # 尝试从回退模块导入
    try:
        from .fallback.psutil_fallback import *
        PSUTIL_AVAILABLE = False
    except ImportError:
        PSUTIL_AVAILABLE = False
        print("⚠️  psutil不可用，性能监控功能受限")

import gc
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
import logging
from collections import defaultdict, deque
import statistics
from pathlib import Path
import json
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float = field(default_factory=time.time)
    
    # CPU使用率
    cpu_percent: float = 0.0
    cpu_count: int = 0
    
    # 内存使用
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    
    # 磁盘I/O
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    
    # 网络I/O
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    
    # 爬取指标
    requests_per_second: float = 0.0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    
    # 连接池指标
    connection_pool_size: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    
    # 缓存指标
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    cache_size_mb: float = 0.0
    
    # Python内存
    python_objects: int = 0
    python_garbage: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used_mb': self.memory_used_mb,
            'requests_per_second': self.requests_per_second,
            'success_rate': self.success_rate,
            'cache_hit_rate': self.cache_hit_rate,
            'active_connections': self.active_connections
        }

@dataclass
class PerformanceThresholds:
    """性能阈值"""
    # CPU
    cpu_warning: float = 80.0  # CPU使用率警告阈值
    cpu_critical: float = 95.0  # CPU使用率危险阈值
    
    # 内存
    memory_warning: float = 80.0  # 内存使用率警告阈值
    memory_critical: float = 95.0  # 内存使用率危险阈值
    
    # 爬取性能
    min_success_rate: float = 70.0  # 最低成功率
    max_response_time: float = 10.0  # 最大响应时间（秒）
    min_requests_per_second: float = 0.5  # 最低请求速率
    
    # 缓存
    min_cache_hit_rate: float = 50.0  # 最低缓存命中率
    
    # 连接池
    max_connections_per_host: int = 6  # 每主机最大连接数
    max_total_connections: int = 20  # 最大总连接数

@dataclass
class OptimizationAction:
    """优化动作"""
    action_id: str
    action_type: str  # adjust, reconfigure, cleanup, alert
    description: str
    priority: int  # 1-10，越高越紧急
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_impact: str = ""
    risk_level: str = "low"  # low, medium, high
    
    def execute(self, optimizer: 'PerformanceOptimizer') -> bool:
        """执行优化动作"""
        try:
            logger.info(f"执行优化动作: {self.description}")
            
            if self.action_type == "adjust":
                return self._execute_adjustment(optimizer)
            elif self.action_type == "reconfigure":
                return self._execute_reconfiguration(optimizer)
            elif self.action_type == "cleanup":
                return self._execute_cleanup(optimizer)
            elif self.action_type == "alert":
                return self._execute_alert(optimizer)
            else:
                logger.warning(f"未知的动作类型: {self.action_type}")
                return False
                
        except Exception as e:
            logger.error(f"执行优化动作失败: {e}")
            return False
    
    def _execute_adjustment(self, optimizer: 'PerformanceOptimizer') -> bool:
        """执行调整动作"""
        # 这里可以实现具体的调整逻辑
        # 例如调整连接池大小、缓存大小等
        logger.info(f"执行调整: {self.parameters}")
        return True
    
    def _execute_reconfiguration(self, optimizer: 'PerformanceOptimizer') -> bool:
        """执行重新配置动作"""
        logger.info(f"执行重新配置: {self.parameters}")
        return True
    
    def _execute_cleanup(self, optimizer: 'PerformanceOptimizer') -> bool:
        """执行清理动作"""
        logger.info(f"执行清理: {self.parameters}")
        return True
    
    def _execute_alert(self, optimizer: 'PerformanceOptimizer') -> bool:
        """执行警报动作"""
        logger.warning(f"性能警报: {self.description}")
        return True

class ConnectionPoolOptimizer:
    """连接池优化器"""
    
    def __init__(self, max_connections: int = 20, max_per_host: int = 6):
        self.max_connections = max_connections
        self.max_per_host = max_per_host
        self.connection_stats: Dict[str, Dict] = defaultdict(dict)
        
    def analyze_pool_usage(self, active_connections: int, idle_connections: int,
                          total_connections: int) -> Dict[str, Any]:
        """分析连接池使用情况"""
        analysis = {
            'active_connections': active_connections,
            'idle_connections': idle_connections,
            'total_connections': total_connections,
            'utilization_rate': active_connections / max(total_connections, 1),
            'idle_rate': idle_connections / max(total_connections, 1),
            'recommendations': []
        }
        
        # 分析建议
        if active_connections >= self.max_connections * 0.9:
            analysis['recommendations'].append({
                'type': 'warning',
                'message': '连接池接近满载，考虑增加最大连接数',
                'action': 'increase_max_connections'
            })
        
        if idle_connections > self.max_connections * 0.5:
            analysis['recommendations'].append({
                'type': 'info',
                'message': '空闲连接较多，考虑减少连接池大小',
                'action': 'decrease_max_connections'
            })
        
        if active_connections < self.max_connections * 0.3 and total_connections > 10:
            analysis['recommendations'].append({
                'type': 'info',
                'message': '连接池使用率较低，考虑减小连接池',
                'action': 'optimize_pool_size'
            })
        
        return analysis
    
    def optimize_pool_size(self, current_load: float, historical_load: List[float]) -> Tuple[int, int]:
        """优化连接池大小"""
        if not historical_load:
            return self.max_connections, self.max_per_host
        
        avg_load = statistics.mean(historical_load)
        max_load = max(historical_load)
        
        # 基于历史负载调整
        if max_load > 0.9:  # 曾经接近满载
            new_max = min(50, int(self.max_connections * 1.2))  # 增加20%，最多50
        elif avg_load < 0.3:  # 平均负载较低
            new_max = max(10, int(self.max_connections * 0.8))  # 减少20%，最少10
        else:
            new_max = self.max_connections
        
        # 调整每主机连接数
        new_per_host = min(10, max(2, int(new_max / 3)))
        
        return new_max, new_per_host

class CacheOptimizer:
    """缓存优化器"""
    
    def __init__(self, max_cache_size_mb: float = 100.0):
        self.max_cache_size_mb = max_cache_size_mb
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'size': 0,
            'evictions': 0
        }
    
    def analyze_cache_performance(self, hits: int, misses: int, 
                                 cache_size_mb: float) -> Dict[str, Any]:
        """分析缓存性能"""
        total = hits + misses
        hit_rate = hits / total if total > 0 else 0.0
        
        analysis = {
            'hits': hits,
            'misses': misses,
            'hit_rate': hit_rate,
            'cache_size_mb': cache_size_mb,
            'utilization': cache_size_mb / self.max_cache_size_mb,
            'recommendations': []
        }
        
        # 分析建议
        if hit_rate < 0.3:
            analysis['recommendations'].append({
                'type': 'warning',
                'message': f'缓存命中率低 ({hit_rate:.1%})，考虑调整缓存策略',
                'action': 'optimize_cache_strategy'
            })
        
        if cache_size_mb >= self.max_cache_size_mb * 0.9:
            analysis['recommendations'].append({
                'type': 'warning',
                'message': '缓存接近满载，考虑增加缓存大小或清理缓存',
                'action': 'increase_cache_size_or_cleanup'
            })
        
        if hit_rate > 0.8 and cache_size_mb < self.max_cache_size_mb * 0.3:
            analysis['recommendations'].append({
                'type': 'info',
                'message': '缓存效率高但利用率低，可以考虑减少缓存大小',
                'action': 'reduce_cache_size'
            })
        
        return analysis
    
    def optimize_cache_strategy(self, access_patterns: Dict[str, int]) -> Dict[str, Any]:
        """优化缓存策略"""
        # 分析访问模式
        total_accesses = sum(access_patterns.values())
        if total_accesses == 0:
            return {'strategy': 'default', 'ttl': 3600}
        
        # 计算热度分布
        sorted_patterns = sorted(access_patterns.items(), key=lambda x: x[1], reverse=True)
        top_10_percent = sorted_patterns[:len(sorted_patterns) // 10]
        top_accesses = sum(count for _, count in top_10_percent)
        
        hot_ratio = top_accesses / total_accesses
        
        # 根据热度分布调整策略
        if hot_ratio > 0.8:  # 热点数据集中
            return {
                'strategy': 'hotspot',
                'ttl': 7200,  # 较长TTL
                'max_size': self.max_cache_size_mb,
                'eviction_policy': 'lru'
            }
        elif hot_ratio > 0.5:  # 中等热度分布
            return {
                'strategy': 'balanced',
                'ttl': 3600,
                'max_size': self.max_cache_size_mb,
                'eviction_policy': 'lfu'
            }
        else:  # 分散访问
            return {
                'strategy': 'distributed',
                'ttl': 1800,  # 较短TTL
                'max_size': self.max_cache_size_mb * 0.7,  # 较小缓存
                'eviction_policy': 'fifo'
            }

class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self):
        self.memory_history: deque = deque(maxlen=100)
        self.gc_stats = {}
    
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Python对象统计
        import sys
        python_objects = len(gc.get_objects())
        python_garbage = len(gc.garbage)
        
        analysis = {
            'process_rss_mb': memory_info.rss / 1024 / 1024,
            'process_vms_mb': memory_info.vms / 1024 / 1024,
            'python_objects': python_objects,
            'python_garbage': python_garbage,
            'gc_collected': gc.get_count(),
            'recommendations': []
        }
        
        # 记录历史
        self.memory_history.append(analysis['process_rss_mb'])
        
        # 分析建议
        if python_garbage > 1000:
            analysis['recommendations'].append({
                'type': 'warning',
                'message': f'Python垃圾对象较多 ({python_garbage})，建议手动清理',
                'action': 'run_garbage_collection'
            })
        
        if len(self.memory_history) > 10:
            # 检查内存增长趋势
            recent_avg = statistics.mean(list(self.memory_history)[-10:])
            if recent_avg > statistics.mean(list(self.memory_history)[-20:-10]) * 1.5:
                analysis['recommendations'].append({
                    'type': 'warning',
                    'message': '检测到内存增长趋势，可能存在内存泄漏',
                    'action': 'investigate_memory_leak'
                })
        
        return analysis
    
    def optimize_memory(self) -> Dict[str, Any]:
        """执行内存优化"""
        actions = []
        
        # 强制垃圾回收
        before_objects = len(gc.get_objects())
        gc.collect()
        after_objects = len(gc.get_objects())
        freed_objects = before_objects - after_objects
        
        if freed_objects > 0:
            actions.append({
                'action': 'garbage_collection',
                'freed_objects': freed_objects
            })
        
        # 清理Python模块缓存
        import sys
        modules_to_unload = []
        for name, module in list(sys.modules.items()):
            if name.startswith('_') or '.' in name:
                continue
            if hasattr(module, '__file__') and module.__file__:
                modules_to_unload.append(name)
        
        # 不要卸载核心模块，只卸载可能不再需要的
        for name in modules_to_unload[:10]:  # 限制数量
            if name in sys.modules and name not in ['sys', 'os', 'builtins']:
                del sys.modules[name]
                actions.append({
                    'action': 'unload_module',
                    'module': name
                })
        
        return {
            'actions_performed': actions,
            'total_actions': len(actions)
        }

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.thresholds = PerformanceThresholds()
        
        # 组件
        self.connection_optimizer = ConnectionPoolOptimizer()
        self.cache_optimizer = CacheOptimizer()
        self.memory_optimizer = MemoryOptimizer()
        
        # 监控数据
        self.metrics_history: deque = deque(maxlen=1000)
        self.optimization_history: List[Dict] = []
        self.alerts: List[Dict] = []
        
        # 性能分析
        self.performance_baseline: Optional[Dict] = None
        self.bottleneck_analysis: Dict[str, Any] = {}
        
        # 加载配置
        if config_file:
            self._load_config(config_file)
        
        # 监控线程
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        logger.info("性能优化器初始化完成")
    
    def _load_config(self, config_file: str):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if 'thresholds' in config:
                thresholds = config['thresholds']
                for key, value in thresholds.items():
                    if hasattr(self.thresholds, key):
                        setattr(self.thresholds, key, value)
            
            logger.info(f"加载性能配置: {config_file}")
            
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
    
    def collect_metrics(self) -> PerformanceMetrics:
        """收集性能指标"""
        metrics = PerformanceMetrics()
        
        # 系统指标
        metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
        metrics.cpu_count = psutil.cpu_count()
        
        # 内存指标
        memory = psutil.virtual_memory()
        metrics.memory_percent = memory.percent
        metrics.memory_used_mb = memory.used / 1024 / 1024
        metrics.memory_available_mb = memory.available / 1024 / 1024
        
        # 磁盘I/O（需要两次采样计算差值）
        try:
            disk_io = psutil.disk_io_counters()
            metrics.disk_read_mb = disk_io.read_bytes / 1024 / 1024
            metrics.disk_write_mb = disk_io.write_bytes / 1024 / 1024
        except:
            pass
        
        # 网络I/O
        try:
            net_io = psutil.net_io_counters()
            metrics.network_sent_mb = net_io.bytes_sent / 1024 / 1024
            metrics.network_recv_mb = net_io.bytes_recv / 1024 / 1024
        except:
            pass
        
        # Python内存
        metrics.python_objects = len(gc.get_objects())
        metrics.python_garbage = len(gc.garbage)
        
        # 爬取指标（需要从外部传入）
        # 这些指标在update_crawl_metrics中设置
        
        return metrics
    
    def update_crawl_metrics(self, metrics: PerformanceMetrics,
                            requests_per_second: float,
                            success_rate: float,
                            avg_response_time: float,
                            connection_pool_size: int = 0,
                            active_connections: int = 0,
                            idle_connections: int = 0,
                            cache_hits: int = 0,
                            cache_misses: int = 0,
                            cache_size_mb: float = 0.0):
        """更新爬取指标"""
        metrics.requests_per_second = requests_per_second
        metrics.success_rate = success_rate
        metrics.avg_response_time = avg_response_time
        
        metrics.connection_pool_size = connection_pool_size
        metrics.active_connections = active_connections
        metrics.idle_connections = idle_connections
        
        metrics.cache_hits = cache_hits
        metrics.cache_misses = cache_misses
        total_cache = cache_hits + cache_misses
        metrics.cache_hit_rate = cache_hits / total_cache if total_cache > 0 else 0.0
        metrics.cache_size_mb = cache_size_mb
        
        # 添加到历史
        self.metrics_history.append(metrics)
    
    def analyze_performance(self) -> Dict[str, Any]:
        """分析性能"""
        if not self.metrics_history:
            return {'status': 'no_data', 'message': '没有性能数据'}
        
        recent_metrics = list(self.metrics_history)[-10:]  # 最近10个样本
        if len(recent_metrics) < 3:
            return {'status': 'insufficient_data', 'message': '数据不足'}
        
        analysis = {
            'timestamp': time.time(),
            'sample_count': len(recent_metrics),
            'alerts': [],
            'recommendations': [],
            'bottlenecks': [],
            'metrics_summary': {}
        }
        
        # 计算平均指标
        metrics_summary = {}
        for key in ['cpu_percent', 'memory_percent', 'requests_per_second', 
                   'success_rate', 'avg_response_time', 'cache_hit_rate']:
            values = [getattr(m, key, 0) for m in recent_metrics]
            metrics_summary[f'avg_{key}'] = statistics.mean(values)
            metrics_summary[f'max_{key}'] = max(values)
            metrics_summary[f'min_{key}'] = min(values)
        
        analysis['metrics_summary'] = metrics_summary
        
        # 检查阈值违规
        self._check_thresholds(analysis, recent_metrics)
        
        # 分析瓶颈
        self._analyze_bottlenecks(analysis, recent_metrics)
        
        # 生成优化建议
        self._generate_recommendations(analysis, recent_metrics)
        
        return analysis
    
    def _check_thresholds(self, analysis: Dict, metrics: List[PerformanceMetrics]):
        """检查阈值违规"""
        latest = metrics[-1]
        
        # CPU检查
        if latest.cpu_percent > self.thresholds.cpu_critical:
            analysis['alerts'].append({
                'type': 'critical',
                'metric': 'cpu_percent',
                'value': latest.cpu_percent,
                'threshold': self.thresholds.cpu_critical,
                'message': 'CPU使用率超过危险阈值'
            })
        elif latest.cpu_percent > self.thresholds.cpu_warning:
            analysis['alerts'].append({
                'type': 'warning',
                'metric': 'cpu_percent',
                'value': latest.cpu_percent,
                'threshold': self.thresholds.cpu_warning,
                'message': 'CPU使用率超过警告阈值'
            })
        
        # 内存检查
        if latest.memory_percent > self.thresholds.memory_critical:
            analysis['alerts'].append({
                'type': 'critical',
                'metric': 'memory_percent',
                'value': latest.memory_percent,
                'threshold': self.thresholds.memory_critical,
                'message': '内存使用率超过危险阈值'
            })
        elif latest.memory_percent > self.thresholds.memory_warning:
            analysis['alerts'].append({
                'type': 'warning',
                'metric': 'memory_percent',
                'value': latest.memory_percent,
                'threshold': self.thresholds.memory_warning,
                'message': '内存使用率超过警告阈值'
            })
        
        # 爬取性能检查
        if latest.success_rate * 100 < self.thresholds.min_success_rate:
            analysis['alerts'].append({
                'type': 'warning',
                'metric': 'success_rate',
                'value': latest.success_rate * 100,
                'threshold': self.thresholds.min_success_rate,
                'message': '成功率低于最低阈值'
            })
        
        if latest.avg_response_time > self.thresholds.max_response_time:
            analysis['alerts'].append({
                'type': 'warning',
                'metric': 'avg_response_time',
                'value': latest.avg_response_time,
                'threshold': self.thresholds.max_response_time,
                'message': '平均响应时间超过阈值'
            })
        
        if latest.requests_per_second < self.thresholds.min_requests_per_second:
            analysis['alerts'].append({
                'type': 'info',
                'metric': 'requests_per_second',
                'value': latest.requests_per_second,
                'threshold': self.thresholds.min_requests_per_second,
                'message': '请求速率低于阈值'
            })
        
        # 缓存检查
        if latest.cache_hit_rate * 100 < self.thresholds.min_cache_hit_rate:
            analysis['alerts'].append({
                'type': 'warning',
                'metric': 'cache_hit_rate',
                'value': latest.cache_hit_rate * 100,
                'threshold': self.thresholds.min_cache_hit_rate,
                'message': '缓存命中率低于阈值'
            })
    
    def _analyze_bottlenecks(self, analysis: Dict, metrics: List[PerformanceMetrics]):
        """分析性能瓶颈"""
        bottlenecks = []
        
        # 分析响应时间分布
        response_times = [m.avg_response_time for m in metrics]
        avg_response_time = statistics.mean(response_times)
        
        if avg_response_time > 5.0:  # 响应时间慢
            bottlenecks.append({
                'type': 'response_time',
                'severity': 'high',
                'description': '平均响应时间较慢',
                'avg_value': avg_response_time,
                'suggestion': '检查网络连接、目标服务器状态或调整请求延迟'
            })
        
        # 分析CPU使用率
        cpu_usage = [m.cpu_percent for m in metrics]
        avg_cpu = statistics.mean(cpu_usage)
        
        if avg_cpu > 70.0:  # CPU使用率高
            bottlenecks.append({
                'type': 'cpu',
                'severity': 'medium',
                'description': 'CPU使用率较高',
                'avg_value': avg_cpu,
                'suggestion': '减少并发请求数或优化处理逻辑'
            })
        
        # 分析内存使用
        memory_usage = [m.memory_percent for m in metrics]
        avg_memory = statistics.mean(memory_usage)
        
        if avg_memory > 80.0:  # 内存使用率高
            bottlenecks.append({
                'type': 'memory',
                'severity': 'high',
                'description': '内存使用率较高',
                'avg_value': avg_memory,
                'suggestion': '优化内存使用，清理缓存，或增加系统内存'
            })
        
        # 分析缓存命中率
        cache_hit_rates = [m.cache_hit_rate for m in metrics]
        avg_cache_hit = statistics.mean(cache_hit_rates)
        
        if avg_cache_hit < 0.3:  # 缓存命中率低
            bottlenecks.append({
                'type': 'cache',
                'severity': 'medium',
                'description': '缓存命中率较低',
                'avg_value': avg_cache_hit * 100,
                'suggestion': '调整缓存策略或增加缓存大小'
            })
        
        analysis['bottlenecks'] = bottlenecks
    
    def _generate_recommendations(self, analysis: Dict, metrics: List[PerformanceMetrics]):
        """生成优化建议"""
        recommendations = []
        latest = metrics[-1]
        
        # CPU相关建议
        if latest.cpu_percent > 70.0:
            recommendations.append({
                'priority': 7,
                'action': 'reduce_concurrency',
                'description': 'CPU使用率较高，建议减少并发请求数',
                'parameters': {'reduction_percent': 20}
            })
        
        # 内存相关建议
        if latest.memory_percent > 75.0:
            recommendations.append({
                'priority': 8,
                'action': 'cleanup_memory',
                'description': '内存使用率较高，建议清理内存',
                'parameters': {'run_gc': True, 'clear_caches': True}
            })
        
        # 响应时间建议
        if latest.avg_response_time > 3.0:
            recommendations.append({
                'priority': 6,
                'action': 'increase_delay',
                'description': '响应时间较慢，建议增加请求延迟',
                'parameters': {'increase_percent': 30}
            })
        
        # 缓存建议
        if latest.cache_hit_rate < 0.4:
            recommendations.append({
                'priority': 5,
                'action': 'optimize_cache',
                'description': '缓存命中率低，建议优化缓存策略',
                'parameters': {'strategy': 'hotspot', 'ttl': 7200}
            })
        
        # 成功率建议
        if latest.success_rate < 0.7:
            recommendations.append({
                'priority': 9,
                'action': 'adjust_retry_policy',
                'description': '成功率较低，建议调整重试策略',
                'parameters': {'max_retries': 5, 'backoff_factor': 2.0}
            })
        
        # 按优先级排序
        recommendations.sort(key=lambda x: x['priority'], reverse=True)
        analysis['recommendations'] = recommendations[:5]  # 只返回前5个建议
    
    def start_monitoring(self, interval_seconds: int = 60):
        """启动性能监控"""
        if self.monitoring_active:
            logger.warning("监控已经在运行")
            return
        
        self.monitoring_active = True
        
        def monitor_loop():
            while self.monitoring_active:
                try:
                    # 收集指标
                    metrics = self.collect_metrics()
                    self.metrics_history.append(metrics)
                    
                    # 定期分析
                    if len(self.metrics_history) % 10 == 0:  # 每10次分析一次
                        analysis = self.analyze_performance()
                        
                        # 检查是否需要优化
                        if analysis['alerts'] or analysis['recommendations']:
                            self._handle_optimization_opportunity(analysis)
                    
                    time.sleep(interval_seconds)
                    
                except Exception as e:
                    logger.error(f"监控循环出错: {e}")
                    time.sleep(interval_seconds)
        
        self.monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info(f"启动性能监控，间隔: {interval_seconds}秒")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("性能监控已停止")
    
    def _handle_optimization_opportunity(self, analysis: Dict):
        """处理优化机会"""
        # 创建优化动作
        for recommendation in analysis.get('recommendations', []):
            action = OptimizationAction(
                action_id=f"opt_{int(time.time())}_{recommendation['action']}",
                action_type="adjust",
                description=recommendation['description'],
                priority=recommendation['priority'],
                parameters=recommendation.get('parameters', {}),
                estimated_impact="需评估",
                risk_level="medium"
            )
            
            # 执行优化动作
            success = action.execute(self)
            
            # 记录优化历史
            self.optimization_history.append({
                'timestamp': time.time(),
                'action': action.action_id,
                'description': action.description,
                'success': success,
                'analysis_snapshot': analysis
            })
    
    def get_optimization_history(self, limit: int = 20) -> List[Dict]:
        """获取优化历史"""
        return list(self.optimization_history)[-limit:]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.metrics_history:
            return {'status': 'no_data'}
        
        recent_analysis = self.analyze_performance()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'metrics_sample_count': len(self.metrics_history),
            'optimization_history_count': len(self.optimization_history),
            'alerts_count': len(recent_analysis.get('alerts', [])),
            'recommendations_count': len(recent_analysis.get('recommendations', [])),
            'bottlenecks_count': len(recent_analysis.get('bottlenecks', [])),
            'current_status': 'healthy',
            'recent_analysis': recent_analysis,
            'summary': self._generate_summary()
        }
        
        # 确定当前状态
        alerts = recent_analysis.get('alerts', [])
        if any(a['type'] == 'critical' for a in alerts):
            report['current_status'] = 'critical'
        elif any(a['type'] == 'warning' for a in alerts):
            report['current_status'] = 'warning'
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要"""
        if not self.metrics_history:
            return {}
        
        recent = list(self.metrics_history)[-5:]
        
        summary = {
            'avg_cpu_percent': statistics.mean([m.cpu_percent for m in recent]),
            'avg_memory_percent': statistics.mean([m.memory_percent for m in recent]),
            'avg_requests_per_second': statistics.mean([m.requests_per_second for m in recent]),
            'avg_success_rate': statistics.mean([m.success_rate for m in recent]),
            'avg_response_time': statistics.mean([m.avg_response_time for m in recent]),
            'avg_cache_hit_rate': statistics.mean([m.cache_hit_rate for m in recent]),
            'monitoring_active': self.monitoring_active
        }
        
        return summary
    
    def export_report(self, output_file: str):
        """导出报告"""
        try:
            report = self.get_performance_report()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"导出性能报告到: {output_file}")
            
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
    
    def optimize_now(self) -> Dict[str, Any]:
        """立即执行优化"""
        # 收集当前指标
        metrics = self.collect_metrics()
        
        # 分析性能
        analysis = self.analyze_performance()
        
        # 执行优化建议
        actions_performed = []
        for recommendation in analysis.get('recommendations', []):
            if recommendation['priority'] >= 7:  # 只执行高优先级建议
                action = OptimizationAction(
                    action_id=f"manual_opt_{int(time.time())}_{recommendation['action']}",
                    action_type="adjust",
                    description=recommendation['description'],
                    priority=recommendation['priority'],
                    parameters=recommendation.get('parameters', {}),
                    estimated_impact="立即优化",
                    risk_level="low"
                )
                
                success = action.execute(self)
                actions_performed.append({
                    'action': recommendation['action'],
                    'success': success,
                    'description': recommendation['description']
                })
        
        return {
            'timestamp': time.time(),
            'actions_performed': actions_performed,
            'analysis': analysis,
            'metrics': metrics.to_dict()
        }