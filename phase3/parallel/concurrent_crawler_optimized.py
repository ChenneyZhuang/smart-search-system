#!/usr/bin/env python3
"""
优化版并行爬取框架 - 全面增强版
集成智能重试、连接池优化、请求指纹随机化、代理支持、实时监控
"""

import asyncio
import json
import os
import sys
import time
import random
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import aiohttp
import aiohttp.client_exceptions
from enum import Enum
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """重试策略"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR = "linear"
    RANDOM = "random"

class ErrorCategory(Enum):
    """错误分类"""
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    SERVER_ERROR = "server_error"  # 5XX
    CLIENT_ERROR = "client_error"   # 4XX
    CAPTCHA = "captcha"
    PARSING_ERROR = "parsing_error"
    UNKNOWN = "unknown"

@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 基础延迟(秒)
    max_delay: float = 30.0  # 最大延迟(秒)
    jitter: float = 0.3      # 随机抖动比例
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # 错误类别特定的重试策略
    error_retry_map: Dict[ErrorCategory, Tuple[int, float]] = field(default_factory=lambda: {
        ErrorCategory.NETWORK_TIMEOUT: (5, 2.0),      # 网络超时: 重试5次，基础延迟2秒
        ErrorCategory.NETWORK_ERROR: (3, 1.0),        # 网络错误: 重试3次
        ErrorCategory.SERVER_ERROR: (2, 5.0),         # 服务器错误: 重试2次，延迟5秒
        ErrorCategory.CLIENT_ERROR: (1, 0.0),         # 客户端错误: 不重试
        ErrorCategory.CAPTCHA: (2, 10.0),            # 验证码: 重试2次，延迟10秒
    })

@dataclass
class ConnectionPoolConfig:
    """连接池配置"""
    max_connections: int = 20
    max_connections_per_host: int = 6
    keepalive_timeout: float = 30.0
    enable_cleanup: bool = True
    cleanup_interval: float = 300.0  # 5分钟清理一次
    
@dataclass
class FingerprintConfig:
    """请求指纹配置"""
    user_agents: List[str] = field(default_factory=lambda: [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ])
    
    accept_languages: List[str] = field(default_factory=lambda: [
        "en-US,en;q=0.9",
        "zh-CN,zh;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en;q=0.8",
        "ko-KR,ko;q=0.9,en;q=0.8",
        "de-DE,de;q=0.9,en;q=0.8",
    ])
    
    referers: List[str] = field(default_factory=lambda: [
        "https://www.google.com/",
        "https://www.bing.com/",
        "https://duckduckgo.com/",
        "https://www.reddit.com/",
        "https://news.ycombinator.com/",
        "https://github.com/",
    ])
    
    enable_random_delay: bool = True
    min_delay: float = 1.0  # 最小延迟(秒)
    max_delay: float = 5.0  # 最大延迟(秒)

@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    proxies: List[str] = field(default_factory=list)
    rotation_strategy: str = "round_robin"  # round_robin, random, failover
    max_failures: int = 3  # 代理失败次数阈值
    health_check_interval: float = 60.0  # 健康检查间隔(秒)

@dataclass
class CrawlResult:
    """爬取结果"""
    source: str  # 方案名称
    success: bool
    data: Dict = None
    error: str = ""
    error_category: ErrorCategory = ErrorCategory.UNKNOWN
    elapsed: float = 0.0
    metadata: Dict = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.data is None:
            self.data = {}

@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    avg_response_time: float = 0.0
    error_distribution: Dict[ErrorCategory, int] = field(default_factory=dict)
    retry_statistics: Dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0, 2: 0, 3: 0})
    
    def update(self, result: CrawlResult):
        self.total_requests += 1
        if result.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.error_distribution[result.error_category] = self.error_distribution.get(result.error_category, 0) + 1
        
        self.total_time += result.elapsed
        self.avg_response_time = self.total_time / self.total_requests
        
        if result.retry_count in self.retry_statistics:
            self.retry_statistics[result.retry_count] += 1

class SmartRetryManager:
    """智能重试管理器"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.error_history = []  # 记录错误历史用于分析
        
    def should_retry(self, error_category: ErrorCategory, retry_count: int) -> bool:
        """判断是否应该重试"""
        if error_category == ErrorCategory.CLIENT_ERROR:
            return False  # 客户端错误不重试
        
        max_retries_for_error = self.config.error_retry_map.get(error_category, (self.config.max_retries, self.config.base_delay))[0]
        return retry_count < max_retries_for_error
    
    def get_delay(self, error_category: ErrorCategory, retry_count: int) -> float:
        """计算重试延迟"""
        base_delay_for_error = self.config.error_retry_map.get(error_category, (self.config.max_retries, self.config.base_delay))[1]
        
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay_for_error * (2 ** retry_count)
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = base_delay_for_error * (retry_count + 1)
        else:  # RANDOM
            delay = base_delay_for_error * (1 + random.random())
        
        # 添加随机抖动
        jitter = delay * self.config.jitter * (random.random() * 2 - 1)  # ±jitter
        delay += jitter
        
        # 限制最大延迟
        return min(delay, self.config.max_delay)
    
    def record_error(self, error_category: ErrorCategory, url: str):
        """记录错误历史"""
        self.error_history.append({
            "timestamp": time.time(),
            "error_category": error_category,
            "url": url
        })
        # 保持最近1000条记录
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]

class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self, config: ConnectionPoolConfig):
        self.config = config
        self.session = None
        self.last_cleanup = time.time()
        
    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建会话"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections_per_host,
                keepalive_timeout=self.config.keepalive_timeout,
                enable_cleanup_closed=self.config.enable_cleanup
            )
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            logger.info(f"创建新的HTTP会话: max_connections={self.config.max_connections}, per_host={self.config.max_connections_per_host}")
        
        # 定期清理
        if self.config.enable_cleanup and time.time() - self.last_cleanup > self.config.cleanup_interval:
            await self.cleanup()
            self.last_cleanup = time.time()
            
        return self.session
    
    async def cleanup(self):
        """清理连接池"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("连接池已清理")
    
    async def close(self):
        """关闭连接池"""
        if self.session:
            await self.session.close()
            self.session = None

class FingerprintManager:
    """指纹管理器"""
    
    def __init__(self, config: FingerprintConfig):
        self.config = config
        self.current_index = 0
        
    def get_headers(self, url: str = None) -> Dict[str, str]:
        """生成随机请求头"""
        headers = {
            "User-Agent": random.choice(self.config.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(self.config.accept_languages),
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        # 添加Referer
        if url and random.random() > 0.3:  # 70%的概率添加Referer
            referer = random.choice(self.config.referers)
            headers["Referer"] = referer
        
        # 随机延迟
        if self.config.enable_random_delay:
            delay = random.uniform(self.config.min_delay, self.config.max_delay)
            time.sleep(delay)
            
        return headers
    
    def rotate_fingerprint(self):
        """轮换指纹"""
        self.current_index = (self.current_index + 1) % len(self.config.user_agents)

class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.proxies = config.proxies.copy()
        self.current_index = 0
        self.proxy_stats = {proxy: {"success": 0, "failures": 0, "last_used": 0} for proxy in self.proxies}
        self.last_health_check = time.time()
        
    def get_proxy(self) -> Optional[str]:
        """获取代理"""
        if not self.config.enabled or not self.proxies:
            return None
            
        # 健康检查
        if time.time() - self.last_health_check > self.config.health_check_interval:
            self._health_check()
            self.last_health_check = time.time()
        
        if self.config.rotation_strategy == "round_robin":
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
        elif self.config.rotation_strategy == "random":
            proxy = random.choice(self.proxies)
        else:  # failover
            # 选择失败次数最少的代理
            proxy = min(self.proxy_stats.items(), key=lambda x: x[1]["failures"])[0]
            
        return proxy
    
    def record_result(self, proxy: str, success: bool):
        """记录代理使用结果"""
        if proxy in self.proxy_stats:
            if success:
                self.proxy_stats[proxy]["success"] += 1
                self.proxy_stats[proxy]["failures"] = max(0, self.proxy_stats[proxy]["failures"] - 1)
            else:
                self.proxy_stats[proxy]["failures"] += 1
            self.proxy_stats[proxy]["last_used"] = time.time()
    
    def _health_check(self):
        """健康检查"""
        unhealthy_proxies = []
        for proxy, stats in self.proxy_stats.items():
            if stats["failures"] >= self.config.max_failures:
                unhealthy_proxies.append(proxy)
                logger.warning(f"代理 {proxy} 失败次数过多: {stats['failures']}")
        
        # 移除不健康的代理
        for proxy in unhealthy_proxies:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                logger.info(f"移除不健康代理: {proxy}")

class CrawlStrategy:
    """爬取策略基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.timeout = 30
        self.retry_manager = SmartRetryManager(RetryConfig())
        
    async def execute(self, url: str) -> CrawlResult:
        """执行爬取"""
        raise NotImplementedError
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """分类错误"""
        error_str = str(error).lower()
        
        if isinstance(error, (asyncio.TimeoutError, aiohttp.ServerTimeoutError)):
            return ErrorCategory.NETWORK_TIMEOUT
        elif isinstance(error, (aiohttp.ClientConnectionError, aiohttp.ClientOSError)):
            return ErrorCategory.NETWORK_ERROR
        elif isinstance(error, aiohttp.ClientResponseError):
            if 500 <= error.status < 600:
                return ErrorCategory.SERVER_ERROR
            elif 400 <= error.status < 500:
                return ErrorCategory.CLIENT_ERROR
        elif "captcha" in error_str or "验证码" in error_str:
            return ErrorCategory.CAPTCHA
        
        return ErrorCategory.UNKNOWN

class HttpFastStrategy(CrawlStrategy):
    """HTTP快速策略（优化版）"""
    
    def __init__(self, connection_pool: ConnectionPoolManager, 
                 fingerprint_manager: FingerprintManager,
                 proxy_manager: ProxyManager):
        super().__init__("http_fast_optimized")
        self.timeout = 25
        self.connection_pool = connection_pool
        self.fingerprint_manager = fingerprint_manager
        self.proxy_manager = proxy_manager
        self.retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        self.retry_manager = SmartRetryManager(self.retry_config)
        
    async def execute_with_retry(self, url: str, retry_count: int = 0) -> CrawlResult:
        """带重试的执行"""
        start_time = time.time()
        
        try:
            session = await self.connection_pool.get_session()
            headers = self.fingerprint_manager.get_headers(url)
            proxy = self.proxy_manager.get_proxy()
            
            request_args = {
                "url": url,
                "headers": headers,
                "timeout": aiohttp.ClientTimeout(total=self.timeout)
            }
            
            if proxy:
                request_args["proxy"] = proxy
                
            async with session.get(**request_args) as response:
                elapsed = time.time() - start_time
                
                if response.status == 200:
                    text = await response.text()
                    
                    # 记录代理结果
                    if proxy:
                        self.proxy_manager.record_result(proxy, True)
                    
                    return CrawlResult(
                        source=self.name,
                        success=True,
                        data={"content": text, "status": response.status},
                        elapsed=elapsed,
                        retry_count=retry_count,
                        metadata={
                            "status_code": response.status,
                            "proxy_used": proxy,
                            "headers_sent": headers
                        }
                    )
                else:
                    error_msg = f"HTTP {response.status}"
                    error_category = self._categorize_error(
                        aiohttp.ClientResponseError(request_info=None, history=None, status=response.status)
                    )
                    
                    # 记录代理结果
                    if proxy:
                        self.proxy_manager.record_result(proxy, False)
                    
                    self.retry_manager.record_error(error_category, url)
                    
                    # 检查是否需要重试
                    if self.retry_manager.should_retry(error_category, retry_count):
                        delay = self.retry_manager.get_delay(error_category, retry_count)
                        logger.info(f"请求失败，{delay:.1f}秒后重试 (第{retry_count+1}次): {error_msg}")
                        await asyncio.sleep(delay)
                        return await self.execute_with_retry(url, retry_count + 1)
                    
                    return CrawlResult(
                        source=self.name,
                        success=False,
                        error=error_msg,
                        error_category=error_category,
                        elapsed=elapsed,
                        retry_count=retry_count,
                        metadata={
                            "status_code": response.status,
                            "proxy_used": proxy
                        }
                    )
                    
        except Exception as e:
            elapsed = time.time() - start_time
            error_category = self._categorize_error(e)
            
            # 记录代理结果
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                self.proxy_manager.record_result(proxy, False)
            
            self.retry_manager.record_error(error_category, url)
            
            # 检查是否需要重试
            if self.retry_manager.should_retry(error_category, retry_count):
                delay = self.retry_manager.get_delay(error_category, retry_count)
                logger.info(f"请求异常，{delay:.1f}秒后重试 (第{retry_count+1}次): {str(e)[:100]}")
                await asyncio.sleep(delay)
                return await self.execute_with_retry(url, retry_count + 1)
            
            return CrawlResult(
                source=self.name,
                success=False,
                error=str(e),
                error_category=error_category,
                elapsed=elapsed,
                retry_count=retry_count,
                metadata={
                    "proxy_used": proxy,
                    "exception_type": type(e).__name__
                }
            )
    
    async def execute(self, url: str) -> CrawlResult:
        """执行爬取（入口）"""
        return await self.execute_with_retry(url)

class ConcurrentCrawlerOptimized:
    """优化版并发爬取器"""
    
    def __init__(self, 
                 retry_config: RetryConfig = None,
                 connection_config: ConnectionPoolConfig = None,
                 fingerprint_config: FingerprintConfig = None,
                 proxy_config: ProxyConfig = None):
        
        # 配置
        self.retry_config = retry_config or RetryConfig()
        self.connection_config = connection_config or ConnectionPoolConfig()
        self.fingerprint_config = fingerprint_config or FingerprintConfig()
        self.proxy_config = proxy_config or ProxyConfig()
        
        # 管理器
        self.connection_pool = ConnectionPoolManager(self.connection_config)
        self.fingerprint_manager = FingerprintManager(self.fingerprint_config)
        self.proxy_manager = ProxyManager(self.proxy_config)
        self.retry_manager = SmartRetryManager(self.retry_config)
        
        # 策略
        self.strategies = []
        
        # 性能监控
        self.metrics = PerformanceMetrics()
        self.start_time = time.time()
        
        logger.info("优化版并发爬取器初始化完成")
        
    def add_strategy(self, strategy: CrawlStrategy):
        """添加爬取策略"""
        self.strategies.append(strategy)
        logger.info(f"添加策略: {strategy.name}")
        
    async def crawl(self, url: str, timeout: float = 30.0) -> CrawlResult:
        """执行爬取（使用最快成功的策略）"""
        if not self.strategies:
            raise ValueError("未添加任何爬取策略")
        
        tasks = []
        for strategy in self.strategies:
            task = asyncio.create_task(strategy.execute(url))
            tasks.append((strategy.name, task))
        
        # 等待第一个完成的任务
        done, pending = await asyncio.wait(
            [task for _, task in tasks],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消未完成的任务
        for _, task in tasks:
            if not task.done():
                task.cancel()
        
        # 处理结果
        results = []
        for task_name, task in tasks:
            if task.done() and not task.cancelled():
                try:
                    result = task.result()
                    results.append(result)
                    
                    # 更新指标
                    self.metrics.update(result)
                    
                    if result.success:
                        logger.info(f"策略 {task_name} 成功: {result.elapsed:.2f}s")
                        return result
                    else:
                        logger.warning(f"策略 {task_name} 失败: {result.error}")
                except Exception as e:
                    logger.error(f"策略 {task_name} 异常: {e}")
        
        # 如果没有成功结果，返回第一个失败结果
        if results:
            return results[0]
        
        # 所有任务都失败
        return CrawlResult(
            source="concurrent_crawler",
            success=False,
            error="所有爬取策略均失败",
            error_category=ErrorCategory.UNKNOWN,
            elapsed=timeout
        )
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        uptime = time.time() - self.start_time
        success_rate = (self.metrics.successful_requests / self.metrics.total_requests * 100) if self.metrics.total_requests > 0 else 0
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate_percent": success_rate,
            "avg_response_time": self.metrics.avg_response_time,
            "error_distribution": {k.value: v for k, v in self.metrics.error_distribution.items()},
            "retry_statistics": self.metrics.retry_statistics
        }
    
    async def close(self):
        """关闭资源"""
        await self.connection_pool.close()
        logger.info("优化版并发爬取器已关闭")

# 快捷函数
async def create_optimized_crawler() -> ConcurrentCrawlerOptimized:
    """创建优化版爬取器（快捷方式）"""
    crawler = ConcurrentCrawlerOptimized(
        retry_config=RetryConfig(max_retries=3, base_delay=1.0),
        connection_config=ConnectionPoolConfig(max_connections=20, max_connections_per_host=6),
        fingerprint_config=FingerprintConfig(),
        proxy_config=ProxyConfig(enabled=False)
    )
    
    # 添加HTTP策略
    http_strategy = HttpFastStrategy(
        crawler.connection_pool,
        crawler.fingerprint_manager,
        crawler.proxy_manager
    )
    crawler.add_strategy(http_strategy)
    
    return crawler

# 使用示例
async def example_usage():
    """使用示例"""
    crawler = await create_optimized_crawler()
    
    try:
        # 测试爬取
        result = await crawler.crawl("https://httpbin.org/get")
        
        if result.success:
            print(f"✅ 爬取成功: {result.elapsed:.2f}s")
            print(f"   数据大小: {len(str(result.data))} 字符")
        else:
            print(f"❌ 爬取失败: {result.error}")
            print(f"   错误类别: {result.error_category.value}")
        
        # 查看统计
        stats = crawler.get_stats()
        print(f"\n📊 统计信息:")
        print(f"   总请求: {stats['total_requests']}")
        print(f"   成功率: {stats['success_rate_percent']:.1f}%")
        print(f"   平均响应时间: {stats['avg_response_time']:.2f}s")
        
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(example_usage())