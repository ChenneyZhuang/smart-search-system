#!/usr/bin/env python3
"""
自适应爬取器 - 根据网站响应动态调整爬取策略
智能调整延迟、并发、重试策略，优化爬取效率和成功率
"""

import time
import json
import statistics
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
import logging
from pathlib import Path
from collections import defaultdict, deque
import hashlib
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

@dataclass
class CrawlMetrics:
    """爬取指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0  # 总响应时间（秒）
    
    # 状态码分布
    status_codes: Dict[int, int] = field(default_factory=dict)
    
    # 错误类型
    error_types: Dict[str, int] = field(default_factory=dict)
    
    # 时间窗口指标（用于计算近期表现）
    recent_success_rate: float = 0.0
    recent_avg_response_time: float = 0.0
    recent_error_rate: float = 0.0
    
    # 时间戳
    first_request_time: Optional[float] = None
    last_request_time: Optional[float] = None
    
    def update(self, success: bool, response_time: float, 
               status_code: Optional[int] = None, error_type: Optional[str] = None):
        """更新指标"""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.total_response_time += response_time
        
        if status_code is not None:
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        
        if error_type is not None:
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
        
        # 更新时间戳
        current_time = time.time()
        if self.first_request_time is None:
            self.first_request_time = current_time
        self.last_request_time = current_time
    
    @property
    def success_rate(self) -> float:
        """总体成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests
    
    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': self.success_rate,
            'avg_response_time': self.avg_response_time,
            'error_rate': self.error_rate,
            'status_codes': self.status_codes,
            'error_types': self.error_types,
            'first_request_time': self.first_request_time,
            'last_request_time': self.last_request_time
        }

@dataclass
class AdaptiveConfig:
    """自适应配置"""
    # 基础配置
    base_delay_min: float = 1.0
    base_delay_max: float = 3.0
    base_concurrent: int = 3
    
    # 调整参数
    min_delay: float = 0.5
    max_delay: float = 10.0
    min_concurrent: int = 1
    max_concurrent: int = 10
    
    # 调整阈值
    success_rate_threshold_low: float = 0.7
    success_rate_threshold_high: float = 0.9
    response_time_threshold_fast: float = 2.0
    response_time_threshold_slow: float = 5.0
    
    # 学习参数
    learning_rate: float = 0.1  # 学习率
    exploration_rate: float = 0.1  # 探索率（随机尝试新策略）
    exploration_decay: float = 0.995  # 探索率衰减
    
    # 时间窗口
    time_window_minutes: int = 30  # 统计时间窗口
    recent_requests_window: int = 50  # 近期请求窗口大小
    
    # 惩罚/奖励
    success_reward: float = 0.1
    failure_penalty: float = 0.2
    fast_response_reward: float = 0.05
    slow_response_penalty: float = 0.1
    
    def __post_init__(self):
        # 确保配置合理
        self.min_delay = max(0.1, self.min_delay)
        self.max_delay = max(self.min_delay, self.max_delay)
        self.min_concurrent = max(1, self.min_concurrent)
        self.max_concurrent = max(self.min_concurrent, self.max_concurrent)

@dataclass
class WebsiteProfile:
    """网站特征档案"""
    domain: str
    metrics: CrawlMetrics = field(default_factory=CrawlMetrics)
    
    # 当前策略
    current_delay_min: float = 1.0
    current_delay_max: float = 3.0
    current_concurrent: int = 3
    
    # 策略历史
    strategy_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 特征
    is_rate_limited: bool = False
    is_cloudflare_protected: bool = False
    requires_javascript: bool = False
    average_page_size: int = 0
    preferred_user_agents: List[str] = field(default_factory=list)
    
    # 学习状态
    exploration_rate: float = 0.1
    last_updated: float = field(default_factory=time.time)
    
    def update_strategy(self, delay_min: float, delay_max: float, concurrent: int):
        """更新策略"""
        self.current_delay_min = delay_min
        self.current_delay_max = delay_max
        self.current_concurrent = concurrent
        
        # 记录历史
        self.strategy_history.append({
            'timestamp': time.time(),
            'delay_min': delay_min,
            'delay_max': delay_max,
            'concurrent': concurrent,
            'success_rate': self.metrics.success_rate,
            'avg_response_time': self.metrics.avg_response_time
        })
        
        # 限制历史长度
        if len(self.strategy_history) > 100:
            self.strategy_history = self.strategy_history[-100:]
        
        self.last_updated = time.time()
    
    def get_random_delay(self) -> float:
        """获取随机延迟"""
        return random.uniform(self.current_delay_min, self.current_delay_max)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'domain': self.domain,
            'metrics': self.metrics.to_dict(),
            'current_delay_min': self.current_delay_min,
            'current_delay_max': self.current_delay_max,
            'current_concurrent': self.current_concurrent,
            'is_rate_limited': self.is_rate_limited,
            'is_cloudflare_protected': self.is_cloudflare_protected,
            'requires_javascript': self.requires_javascript,
            'exploration_rate': self.exploration_rate,
            'last_updated': self.last_updated,
            'strategy_history_count': len(self.strategy_history)
        }

class AdaptiveCrawler:
    """自适应爬取器"""
    
    def __init__(self, config: Optional[AdaptiveConfig] = None,
                 profile_storage: str = "./adaptive_profiles"):
        """
        初始化自适应爬取器
        
        Args:
            config: 自适应配置
            profile_storage: 网站档案存储目录
        """
        self.config = config or AdaptiveConfig()
        self.profile_storage = Path(profile_storage)
        self.profile_storage.mkdir(parents=True, exist_ok=True)
        
        # 网站档案
        self.profiles: Dict[str, WebsiteProfile] = {}
        
        # 近期请求记录（用于计算近期指标）
        self.recent_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.config.recent_requests_window))
        
        # 加载现有档案
        self._load_profiles()
        
        logger.info(f"自适应爬取器初始化完成，配置: {self.config}")
    
    def _load_profiles(self):
        """加载网站档案"""
        for file_path in self.profile_storage.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                domain = data['domain']
                profile = WebsiteProfile(domain=domain)
                
                # 加载指标
                if 'metrics' in data:
                    metrics_data = data['metrics']
                    profile.metrics.total_requests = metrics_data.get('total_requests', 0)
                    profile.metrics.successful_requests = metrics_data.get('successful_requests', 0)
                    profile.metrics.failed_requests = metrics_data.get('failed_requests', 0)
                    profile.metrics.total_response_time = metrics_data.get('total_response_time', 0.0)
                    profile.metrics.status_codes = metrics_data.get('status_codes', {})
                    profile.metrics.error_types = metrics_data.get('error_types', {})
                
                # 加载策略
                profile.current_delay_min = data.get('current_delay_min', self.config.base_delay_min)
                profile.current_delay_max = data.get('current_delay_max', self.config.base_delay_max)
                profile.current_concurrent = data.get('current_concurrent', self.config.base_concurrent)
                
                # 加载特征
                profile.is_rate_limited = data.get('is_rate_limited', False)
                profile.is_cloudflare_protected = data.get('is_cloudflare_protected', False)
                profile.requires_javascript = data.get('requires_javascript', False)
                profile.exploration_rate = data.get('exploration_rate', self.config.exploration_rate)
                
                self.profiles[domain] = profile
                
                logger.debug(f"加载网站档案: {domain}")
                
            except Exception as e:
                logger.warning(f"加载档案失败 {file_path}: {e}")
    
    def _save_profile(self, profile: WebsiteProfile):
        """保存网站档案"""
        try:
            file_path = self.profile_storage / f"{profile.domain}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存档案失败 {profile.domain}: {e}")
    
    def get_domain(self, url: str) -> str:
        """从URL获取域名"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            # 如果解析失败，返回整个URL的哈希值
            return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def get_profile(self, url: str) -> WebsiteProfile:
        """获取网站档案（如果不存在则创建）"""
        domain = self.get_domain(url)
        
        if domain not in self.profiles:
            # 创建新档案
            profile = WebsiteProfile(domain=domain)
            profile.current_delay_min = self.config.base_delay_min
            profile.current_delay_max = self.config.base_delay_max
            profile.current_concurrent = self.config.base_concurrent
            profile.exploration_rate = self.config.exploration_rate
            
            self.profiles[domain] = profile
            
            logger.debug(f"创建新网站档案: {domain}")
        
        return self.profiles[domain]
    
    def record_request(self, url: str, success: bool, response_time: float,
                      status_code: Optional[int] = None, error_type: Optional[str] = None):
        """记录请求结果"""
        domain = self.get_domain(url)
        profile = self.get_profile(url)
        
        # 更新总体指标
        profile.metrics.update(success, response_time, status_code, error_type)
        
        # 更新近期请求记录
        recent_record = {
            'timestamp': time.time(),
            'success': success,
            'response_time': response_time,
            'status_code': status_code
        }
        self.recent_requests[domain].append(recent_record)
        
        # 计算近期指标
        self._update_recent_metrics(profile)
        
        # 自适应调整策略
        self._adapt_strategy(profile)
        
        # 更新探索率
        profile.exploration_rate *= self.config.exploration_decay
        profile.exploration_rate = max(0.01, profile.exploration_rate)
        
        # 保存档案
        self._save_profile(profile)
    
    def _update_recent_metrics(self, profile: WebsiteProfile):
        """更新近期指标"""
        domain = profile.domain
        recent = list(self.recent_requests[domain])
        
        if not recent:
            profile.metrics.recent_success_rate = 0.0
            profile.metrics.recent_avg_response_time = 0.0
            profile.metrics.recent_error_rate = 0.0
            return
        
        # 计算近期成功率
        successful = sum(1 for r in recent if r.get('success', False))
        profile.metrics.recent_success_rate = successful / len(recent)
        
        # 计算近期平均响应时间
        response_times = [r.get('response_time', 0.0) for r in recent]
        profile.metrics.recent_avg_response_time = statistics.mean(response_times) if response_times else 0.0
        
        # 计算近期错误率
        profile.metrics.recent_error_rate = 1.0 - profile.metrics.recent_success_rate
    
    def _adapt_strategy(self, profile: WebsiteProfile):
        """自适应调整策略"""
        # 获取当前指标
        success_rate = profile.metrics.recent_success_rate
        avg_response_time = profile.metrics.recent_avg_response_time
        
        # 检查是否需要探索新策略
        if random.random() < profile.exploration_rate:
            self._explore_new_strategy(profile)
            return
        
        # 基于当前表现调整策略
        new_delay_min = profile.current_delay_min
        new_delay_max = profile.current_delay_max
        new_concurrent = profile.current_concurrent
        
        # 调整延迟
        if success_rate < self.config.success_rate_threshold_low:
            # 成功率低，增加延迟
            new_delay_min = min(self.config.max_delay, new_delay_min * 1.5)
            new_delay_max = min(self.config.max_delay, new_delay_max * 1.5)
            logger.debug(f"成功率低 ({success_rate:.2f})，增加延迟: {new_delay_min:.2f}-{new_delay_max:.2f}s")
        
        elif success_rate > self.config.success_rate_threshold_high:
            # 成功率高，尝试减少延迟
            new_delay_min = max(self.config.min_delay, new_delay_min * 0.8)
            new_delay_max = max(self.config.min_delay, new_delay_max * 0.8)
            logger.debug(f"成功率高 ({success_rate:.2f})，减少延迟: {new_delay_min:.2f}-{new_delay_max:.2f}s")
        
        # 调整响应时间
        if avg_response_time > self.config.response_time_threshold_slow:
            # 响应时间慢，减少并发
            new_concurrent = max(self.config.min_concurrent, new_concurrent - 1)
            logger.debug(f"响应时间慢 ({avg_response_time:.2f}s)，减少并发: {new_concurrent}")
        
        elif avg_response_time < self.config.response_time_threshold_fast and success_rate > 0.8:
            # 响应时间快且成功率高，尝试增加并发
            new_concurrent = min(self.config.max_concurrent, new_concurrent + 1)
            logger.debug(f"响应时间快 ({avg_response_time:.2f}s)，增加并发: {new_concurrent}")
        
        # 检查是否被限速
        if self._detect_rate_limiting(profile):
            profile.is_rate_limited = True
            new_delay_min = max(new_delay_min, 3.0)  # 确保最小延迟
            new_delay_max = max(new_delay_max, 6.0)
            new_concurrent = max(1, new_concurrent - 1)
            logger.warning(f"检测到限速，调整策略: 延迟={new_delay_min:.2f}-{new_delay_max:.2f}s, 并发={new_concurrent}")
        
        # 应用新策略
        profile.update_strategy(new_delay_min, new_delay_max, new_concurrent)
    
    def _explore_new_strategy(self, profile: WebsiteProfile):
        """探索新策略"""
        # 随机调整参数
        exploration_factor = random.uniform(0.8, 1.2)
        
        new_delay_min = max(
            self.config.min_delay,
            min(self.config.max_delay, profile.current_delay_min * exploration_factor)
        )
        
        new_delay_max = max(
            self.config.min_delay,
            min(self.config.max_delay, profile.current_delay_max * exploration_factor)
        )
        
        # 确保min <= max
        if new_delay_min > new_delay_max:
            new_delay_min, new_delay_max = new_delay_max, new_delay_min
        
        # 随机调整并发
        concurrent_change = random.choice([-1, 0, 1])
        new_concurrent = max(
            self.config.min_concurrent,
            min(self.config.max_concurrent, profile.current_concurrent + concurrent_change)
        )
        
        logger.debug(f"探索新策略: 延迟={new_delay_min:.2f}-{new_delay_max:.2f}s, 并发={new_concurrent}")
        
        profile.update_strategy(new_delay_min, new_delay_max, new_concurrent)
    
    def _detect_rate_limiting(self, profile: WebsiteProfile) -> bool:
        """检测是否被限速"""
        # 检查近期状态码
        recent = list(self.recent_requests[profile.domain])
        
        if len(recent) < 10:
            return False
        
        # 检查429（太多请求）状态码
        recent_429 = sum(1 for r in recent if r.get('status_code') == 429)
        if recent_429 > 0:
            return True
        
        # 检查403/404突然增加
        recent_errors = sum(1 for r in recent if not r.get('success', False))
        error_rate = recent_errors / len(recent)
        
        if error_rate > 0.5:  # 错误率超过50%
            return True
        
        # 检查响应时间突然增加
        if len(recent) >= 20:
            # 比较最近10个和之前10个请求
            recent_10 = recent[-10:]
            previous_10 = recent[-20:-10]
            
            if previous_10 and recent_10:
                recent_avg = statistics.mean([r.get('response_time', 0.0) for r in recent_10])
                previous_avg = statistics.mean([r.get('response_time', 0.0) for r in previous_10])
                
                if previous_avg > 0 and recent_avg / previous_avg > 3.0:  # 响应时间增加3倍以上
                    return True
        
        return False
    
    def get_crawl_parameters(self, url: str) -> Dict[str, Any]:
        """获取爬取参数"""
        profile = self.get_profile(url)
        
        # 获取随机延迟
        delay = profile.get_random_delay()
        
        return {
            'delay_seconds': delay,
            'delay_range': (profile.current_delay_min, profile.current_delay_max),
            'concurrent_requests': profile.current_concurrent,
            'exploration_rate': profile.exploration_rate,
            'success_rate': profile.metrics.recent_success_rate,
            'avg_response_time': profile.metrics.recent_avg_response_time,
            'is_rate_limited': profile.is_rate_limited,
            'requires_javascript': profile.requires_javascript
        }
    
    def suggest_initial_strategy(self, url: str) -> Dict[str, Any]:
        """根据URL特征建议初始策略"""
        domain = self.get_domain(url)
        
        # 检查已知网站类型
        if 'indeed' in domain:
            return {
                'delay_min': 2.0,
                'delay_max': 5.0,
                'concurrent': 2,
                'notes': 'Cloudflare protected, be cautious'
            }
        elif 'seek' in domain:
            return {
                'delay_min': 2.0,
                'delay_max': 4.0,
                'concurrent': 2,
                'notes': 'Rate limiting detected'
            }
        elif 'apsjobs' in domain:
            return {
                'delay_min': 1.5,
                'delay_max': 3.0,
                'concurrent': 3,
                'notes': 'Government site, relatively stable'
            }
        elif 'linkedin' in domain:
            return {
                'delay_min': 5.0,
                'delay_max': 10.0,
                'concurrent': 1,
                'notes': 'Very strict anti-crawling'
            }
        else:
            # 默认策略
            return {
                'delay_min': self.config.base_delay_min,
                'delay_max': self.config.base_delay_max,
                'concurrent': self.config.base_concurrent,
                'notes': 'New site, using default strategy'
            }
    
    def analyze_performance(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """分析性能"""
        if domain:
            profiles = [self.profiles.get(domain)]
            profiles = [p for p in profiles if p is not None]
        else:
            profiles = list(self.profiles.values())
        
        if not profiles:
            return {"error": "没有可用的档案"}
        
        analysis = {
            'total_domains': len(profiles),
            'domains': [],
            'overall_metrics': {
                'total_requests': 0,
                'success_rate': 0.0,
                'avg_response_time': 0.0
            },
            'best_performing': [],
            'worst_performing': []
        }
        
        total_requests = 0
        total_successful = 0
        total_response_time = 0.0
        
        domain_metrics = []
        
        for profile in profiles:
            metrics = profile.metrics
            
            domain_metrics.append({
                'domain': profile.domain,
                'total_requests': metrics.total_requests,
                'success_rate': metrics.success_rate,
                'avg_response_time': metrics.avg_response_time,
                'current_delay': f"{profile.current_delay_min:.2f}-{profile.current_delay_max:.2f}s",
                'current_concurrent': profile.current_concurrent,
                'is_rate_limited': profile.is_rate_limited
            })
            
            total_requests += metrics.total_requests
            total_successful += metrics.successful_requests
            total_response_time += metrics.total_response_time
        
        # 总体指标
        if total_requests > 0:
            analysis['overall_metrics']['total_requests'] = total_requests
            analysis['overall_metrics']['success_rate'] = total_successful / total_requests
            analysis['overall_metrics']['avg_response_time'] = total_response_time / total_requests
        
        # 按成功率排序
        domain_metrics.sort(key=lambda x: x['success_rate'], reverse=True)
        analysis['domains'] = domain_metrics
        
        # 最佳和最差表现
        if domain_metrics:
            analysis['best_performing'] = domain_metrics[:3]
            analysis['worst_performing'] = domain_metrics[-3:] if len(domain_metrics) >= 3 else domain_metrics
        
        return analysis
    
    def reset_domain_profile(self, domain: str):
        """重置域名档案"""
        if domain in self.profiles:
            del self.profiles[domain]
            
            # 删除存储文件
            file_path = self.profile_storage / f"{domain}.json"
            if file_path.exists():
                file_path.unlink()
            
            logger.info(f"重置域名档案: {domain}")
    
    def export_profiles(self, output_file: str):
        """导出所有档案"""
        try:
            data = {
                'exported_at': datetime.now().isoformat(),
                'total_profiles': len(self.profiles),
                'config': self.config.__dict__,
                'profiles': {}
            }
            
            for domain, profile in self.profiles.items():
                data['profiles'][domain] = profile.to_dict()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"导出 {len(self.profiles)} 个档案到 {output_file}")
            
        except Exception as e:
            logger.error(f"导出档案失败: {e}")
    
    def get_recommendations(self, url: str) -> Dict[str, Any]:
        """获取爬取建议"""
        profile = self.get_profile(url)
        
        recommendations = {
            'domain': profile.domain,
            'current_strategy': {
                'delay_range': f"{profile.current_delay_min:.2f}-{profile.current_delay_max:.2f}s",
                'concurrent': profile.current_concurrent
            },
            'performance': {
                'success_rate': f"{profile.metrics.success_rate:.1%}",
                'recent_success_rate': f"{profile.metrics.recent_success_rate:.1%}",
                'avg_response_time': f"{profile.metrics.avg_response_time:.2f}s"
            },
            'recommendations': []
        }
        
        # 生成建议
        if profile.metrics.recent_success_rate < 0.5:
            recommendations['recommendations'].append({
                'type': 'critical',
                'message': '成功率过低，建议增加延迟并减少并发',
                'action': 'increase_delay_reduce_concurrency'
            })
        
        if profile.is_rate_limited:
            recommendations['recommendations'].append({
                'type': 'warning',
                'message': '检测到限速，请谨慎爬取',
                'action': 'reduce_aggressiveness'
            })
        
        if profile.metrics.avg_response_time > 5.0:
            recommendations['recommendations'].append({
                'type': 'warning',
                'message': '响应时间较慢，考虑减少并发',
                'action': 'reduce_concurrency'
            })
        
        if profile.metrics.recent_success_rate > 0.9 and profile.metrics.avg_response_time < 2.0:
            recommendations['recommendations'].append({
                'type': 'info',
                'message': '表现良好，可以尝试增加并发',
                'action': 'increase_concurrency'
            })
        
        if not recommendations['recommendations']:
            recommendations['recommendations'].append({
                'type': 'info',
                'message': '当前策略表现正常',
                'action': 'maintain_current'
            })
        
        return recommendations