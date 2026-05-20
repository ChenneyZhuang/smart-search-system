#!/usr/bin/env python3
"""
监控系统 - 实时监控爬取进度、性能指标和错误警报
支持仪表板、实时警报、日志分析和多通道通知
"""

import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
import threading
import statistics
import re

logger = logging.getLogger(__name__)

@dataclass
class MetricDataPoint:
    """指标数据点"""
    timestamp: float
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'metric_name': self.metric_name,
            'value': self.value,
            'tags': self.tags,
            'metadata': self.metadata
        }

@dataclass
class AlertRule:
    """警报规则"""
    rule_id: str
    name: str
    metric_name: str
    condition: str  # >, <, >=, <=, ==, !=, contains, regex
    threshold: Any
    duration_seconds: int = 60  # 持续时间（秒）
    severity: str = "warning"  # info, warning, error, critical
    message_template: str = "{metric_name} {condition} {threshold}"
    tags_filter: Dict[str, str] = field(default_factory=dict)
    cooldown_seconds: int = 300  # 冷却时间（秒）
    enabled: bool = True
    
    def matches(self, datapoint: MetricDataPoint, recent_values: List[float]) -> bool:
        """检查是否匹配"""
        if not self.enabled:
            return False
        
        # 检查标签过滤
        for key, value in self.tags_filter.items():
            if datapoint.tags.get(key) != value:
                return False
        
        # 检查条件
        if self.condition == ">":
            return datapoint.value > self.threshold
        elif self.condition == "<":
            return datapoint.value < self.threshold
        elif self.condition == ">=":
            return datapoint.value >= self.threshold
        elif self.condition == "<=":
            return datapoint.value <= self.threshold
        elif self.condition == "==":
            return datapoint.value == self.threshold
        elif self.condition == "!=":
            return datapoint.value != self.threshold
        elif self.condition == "contains":
            return str(self.threshold) in str(datapoint.value)
        elif self.condition == "regex":
            return bool(re.search(str(self.threshold), str(datapoint.value)))
        
        return False
    
    def get_alert_message(self, datapoint: MetricDataPoint) -> str:
        """获取警报消息"""
        message = self.message_template
        message = message.replace("{metric_name}", self.metric_name)
        message = message.replace("{condition}", self.condition)
        message = message.replace("{threshold}", str(self.threshold))
        message = message.replace("{value}", str(datapoint.value))
        message = message.replace("{timestamp}", datetime.fromtimestamp(datapoint.timestamp).isoformat())
        return message

@dataclass
class Alert:
    """警报"""
    alert_id: str
    rule_id: str
    timestamp: float
    severity: str
    message: str
    metric_value: float
    metric_tags: Dict[str, str]
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'alert_id': self.alert_id,
            'rule_id': self.rule_id,
            'timestamp': self.timestamp,
            'severity': self.severity,
            'message': self.message,
            'metric_value': self.metric_value,
            'metric_tags': self.metric_tags,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at
        }

@dataclass
class NotificationChannel:
    """通知渠道"""
    channel_id: str
    channel_type: str  # console, file, telegram, email, webhook
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    severity_filter: List[str] = field(default_factory=lambda: ["error", "critical"])
    
    def send_notification(self, alert: Alert) -> bool:
        """发送通知"""
        if not self.enabled:
            return False
        
        if alert.severity not in self.severity_filter:
            return False
        
        try:
            if self.channel_type == "console":
                return self._send_to_console(alert)
            elif self.channel_type == "file":
                return self._send_to_file(alert)
            elif self.channel_type == "telegram":
                return self._send_to_telegram(alert)
            elif self.channel_type == "email":
                return self._send_to_email(alert)
            elif self.channel_type == "webhook":
                return self._send_to_webhook(alert)
            else:
                logger.warning(f"未知的通知渠道类型: {self.channel_type}")
                return False
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False
    
    def _send_to_console(self, alert: Alert) -> bool:
        """发送到控制台"""
        color_codes = {
            "info": "\033[94m",    # 蓝色
            "warning": "\033[93m", # 黄色
            "error": "\033[91m",   # 红色
            "critical": "\033[95m" # 紫色
        }
        reset_code = "\033[0m"
        
        color = color_codes.get(alert.severity, "\033[0m")
        timestamp = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"{color}[{timestamp}] [{alert.severity.upper()}] {alert.message}{reset_code}")
        return True
    
    def _send_to_file(self, alert: Alert) -> bool:
        """发送到文件"""
        filepath = self.config.get('filepath', './alerts.log')
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                timestamp = datetime.fromtimestamp(alert.timestamp).isoformat()
                line = f"{timestamp} [{alert.severity}] {alert.message}\n"
                f.write(line)
            return True
        except Exception as e:
            logger.error(f"写入警报文件失败: {e}")
            return False
    
    def _send_to_telegram(self, alert: Alert) -> bool:
        """发送到Telegram"""
        # 这里需要实现Telegram bot集成
        # 暂时返回True表示成功
        logger.info(f"Telegram通知: {alert.message}")
        return True
    
    def _send_to_email(self, alert: Alert) -> bool:
        """发送邮件"""
        # 这里需要实现邮件发送
        logger.info(f"邮件通知: {alert.message}")
        return True
    
    def _send_to_webhook(self, alert: Alert) -> bool:
        """发送到Webhook"""
        # 这里需要实现HTTP webhook
        logger.info(f"Webhook通知: {alert.message}")
        return True

class MetricStore:
    """指标存储"""
    
    def __init__(self, max_points_per_metric: int = 10000):
        self.max_points = max_points_per_metric
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self.lock = threading.RLock()
    
    def add_datapoint(self, datapoint: MetricDataPoint):
        """添加数据点"""
        with self.lock:
            key = self._get_metric_key(datapoint.metric_name, datapoint.tags)
            self.metrics[key].append(datapoint)
    
    def add_datapoints(self, datapoints: List[MetricDataPoint]):
        """批量添加数据点"""
        with self.lock:
            for datapoint in datapoints:
                key = self._get_metric_key(datapoint.metric_name, datapoint.tags)
                self.metrics[key].append(datapoint)
    
    def get_metric_data(self, metric_name: str, tags: Optional[Dict[str, str]] = None,
                       start_time: Optional[float] = None,
                       end_time: Optional[float] = None,
                       limit: Optional[int] = None) -> List[MetricDataPoint]:
        """获取指标数据"""
        with self.lock:
            key = self._get_metric_key(metric_name, tags or {})
            if key not in self.metrics:
                return []
            
            datapoints = list(self.metrics[key])
            
            # 时间过滤
            if start_time is not None:
                datapoints = [dp for dp in datapoints if dp.timestamp >= start_time]
            if end_time is not None:
                datapoints = [dp for dp in datapoints if dp.timestamp <= end_time]
            
            # 限制数量
            if limit is not None and limit > 0:
                datapoints = datapoints[-limit:]
            
            return datapoints
    
    def get_metric_stats(self, metric_name: str, tags: Optional[Dict[str, str]] = None,
                        time_window_seconds: int = 300) -> Dict[str, Any]:
        """获取指标统计"""
        end_time = time.time()
        start_time = end_time - time_window_seconds
        
        datapoints = self.get_metric_data(metric_name, tags, start_time, end_time)
        
        if not datapoints:
            return {'count': 0, 'message': '没有数据'}
        
        values = [dp.value for dp in datapoints]
        
        stats = {
            'count': len(values),
            'avg': statistics.mean(values) if values else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0,
            'sum': sum(values) if values else 0,
            'std': statistics.stdev(values) if len(values) > 1 else 0,
            'latest_value': datapoints[-1].value if datapoints else 0,
            'latest_timestamp': datapoints[-1].timestamp if datapoints else 0,
            'time_window_seconds': time_window_seconds
        }
        
        # 计算变化率（如果数据点足够）
        if len(datapoints) >= 2:
            first_value = datapoints[0].value
            last_value = datapoints[-1].value
            time_diff = datapoints[-1].timestamp - datapoints[0].timestamp
            
            if time_diff > 0:
                stats['rate_per_second'] = (last_value - first_value) / time_diff
            else:
                stats['rate_per_second'] = 0
        else:
            stats['rate_per_second'] = 0
        
        return stats
    
    def get_all_metrics(self) -> List[str]:
        """获取所有指标名称"""
        with self.lock:
            # 提取唯一的指标名称
            metric_names = set()
            for key in self.metrics.keys():
                # 键的格式: metric_name|tag1=value1|tag2=value2
                if '|' in key:
                    metric_name = key.split('|')[0]
                else:
                    metric_name = key
                metric_names.add(metric_name)
            
            return sorted(list(metric_names))
    
    def cleanup_old_data(self, max_age_seconds: int = 86400):
        """清理旧数据"""
        cutoff_time = time.time() - max_age_seconds
        deleted_count = 0
        
        with self.lock:
            for key in list(self.metrics.keys()):
                datapoints = self.metrics[key]
                # 删除旧数据点
                original_count = len(datapoints)
                while datapoints and datapoints[0].timestamp < cutoff_time:
                    datapoints.popleft()
                
                deleted_count += (original_count - len(datapoints))
                
                # 如果指标没有数据了，删除空队列
                if not datapoints:
                    del self.metrics[key]
        
        if deleted_count > 0:
            logger.debug(f"清理了 {deleted_count} 个旧数据点")
        
        return deleted_count
    
    def _get_metric_key(self, metric_name: str, tags: Dict[str, str]) -> str:
        """获取指标键"""
        if not tags:
            return metric_name
        
        # 按字母顺序排序标签，确保一致性
        sorted_tags = sorted(tags.items())
        tag_str = '|'.join([f"{k}={v}" for k, v in sorted_tags])
        return f"{metric_name}|{tag_str}"

class DeepCrawlMonitor:
    """深度爬取监控系统"""
    
    # 预定义的指标名称
    METRICS = {
        # 爬取指标
        'crawl.requests.total': '总请求数',
        'crawl.requests.success': '成功请求数',
        'crawl.requests.failed': '失败请求数',
        'crawl.requests.per_second': '请求速率',
        'crawl.success_rate': '成功率',
        'crawl.response_time.avg': '平均响应时间',
        'crawl.response_time.p95': '95%响应时间',
        'crawl.pages.crawled': '已爬取页面数',
        'crawl.pages.discovered': '已发现页面数',
        'crawl.depth.current': '当前深度',
        
        # 系统指标
        'system.cpu.percent': 'CPU使用率',
        'system.memory.percent': '内存使用率',
        'system.memory.used_mb': '已用内存(MB)',
        'system.disk.used_percent': '磁盘使用率',
        
        # 网络指标
        'network.requests.active': '活跃请求数',
        'network.connections.active': '活跃连接数',
        'network.connections.idle': '空闲连接数',
        
        # 缓存指标
        'cache.hits': '缓存命中数',
        'cache.misses': '缓存未命中数',
        'cache.hit_rate': '缓存命中率',
        'cache.size_mb': '缓存大小(MB)',
        
        # 错误指标
        'errors.http.4xx': 'HTTP 4XX错误',
        'errors.http.5xx': 'HTTP 5XX错误',
        'errors.network': '网络错误',
        'errors.timeout': '超时错误',
        'errors.captcha': '验证码错误',
        
        # 进度指标
        'progress.percentage': '进度百分比',
        'progress.estimated_completion': '预计完成时间',
        'progress.urls_remaining': '剩余URL数'
    }
    
    # 预定义的警报规则
    DEFAULT_ALERT_RULES = [
        AlertRule(
            rule_id="crawl_success_rate_low",
            name="爬取成功率低",
            metric_name="crawl.success_rate",
            condition="<",
            threshold=0.7,
            duration_seconds=60,
            severity="error",
            message_template="爬取成功率低于70%: {value:.1%}"
        ),
        AlertRule(
            rule_id="response_time_high",
            name="响应时间高",
            metric_name="crawl.response_time.avg",
            condition=">",
            threshold=5.0,
            duration_seconds=30,
            severity="warning",
            message_template="平均响应时间超过5秒: {value:.1f}s"
        ),
        AlertRule(
            rule_id="cpu_usage_high",
            name="CPU使用率高",
            metric_name="system.cpu.percent",
            condition=">",
            threshold=80.0,
            duration_seconds=60,
            severity="warning",
            message_template="CPU使用率超过80%: {value:.1f}%"
        ),
        AlertRule(
            rule_id="memory_usage_high",
            name="内存使用率高",
            metric_name="system.memory.percent",
            condition=">",
            threshold=85.0,
            duration_seconds=60,
            severity="warning",
            message_template="内存使用率超过85%: {value:.1f}%"
        ),
        AlertRule(
            rule_id="network_errors_high",
            name="网络错误率高",
            metric_name="errors.network",
            condition=">",
            threshold=10,
            duration_seconds=300,
            severity="error",
            message_template="5分钟内网络错误超过10次: {value}次"
        ),
        AlertRule(
            rule_id="crawl_stalled",
            name="爬取停滞",
            metric_name="crawl.requests.per_second",
            condition="<",
            threshold=0.1,
            duration_seconds=300,
            severity="critical",
            message_template="爬取速率低于0.1请求/秒，可能已停滞"
        )
    ]
    
    def __init__(self, config_file: Optional[str] = None):
        """初始化监控系统"""
        self.config_file = config_file
        
        # 核心组件
        self.metric_store = MetricStore()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, Alert] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        
        # 状态
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.last_cleanup_time = time.time()
        
        # 警报冷却记录
        self.alert_cooldown: Dict[str, float] = {}
        
        # 加载配置
        self._load_default_rules()
        self._load_default_channels()
        
        if config_file:
            self._load_config(config_file)
        
        logger.info(f"监控系统初始化完成: {len(self.alert_rules)}条规则, {len(self.notification_channels)}个通知渠道")
    
    def _load_default_rules(self):
        """加载默认警报规则"""
        for rule in self.DEFAULT_ALERT_RULES:
            self.alert_rules[rule.rule_id] = rule
    
    def _load_default_channels(self):
        """加载默认通知渠道"""
        # 控制台渠道
        console_channel = NotificationChannel(
            channel_id="console",
            channel_type="console",
            name="控制台",
            config={},
            enabled=True,
            severity_filter=["info", "warning", "error", "critical"]
        )
        self.notification_channels["console"] = console_channel
        
        # 文件渠道
        file_channel = NotificationChannel(
            channel_id="file",
            channel_type="file",
            name="日志文件",
            config={"filepath": "./crawl_monitor_alerts.log"},
            enabled=True,
            severity_filter=["error", "critical"]
        )
        self.notification_channels["file"] = file_channel
    
    def _load_config(self, config_file: str):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 加载警报规则
            if 'alert_rules' in config:
                for rule_data in config['alert_rules']:
                    rule = AlertRule(**rule_data)
                    self.alert_rules[rule.rule_id] = rule
            
            # 加载通知渠道
            if 'notification_channels' in config:
                for channel_data in config['notification_channels']:
                    channel = NotificationChannel(**channel_data)
                    self.notification_channels[channel.channel_id] = channel
            
            logger.info(f"从配置文件加载: {config_file}")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    
    def start_monitoring(self, interval_seconds: int = 10):
        """启动监控"""
        if self.monitoring_active:
            logger.warning("监控已经在运行")
            return
        
        self.monitoring_active = True
        
        def monitor_loop():
            while self.monitoring_active:
                try:
                    # 检查警报
                    self._check_alerts()
                    
                    # 定期清理旧数据
                    current_time = time.time()
                    if current_time - self.last_cleanup_time > 3600:  # 每小时清理一次
                        self.metric_store.cleanup_old_data()
                        self.last_cleanup_time = current_time
                    
                    time.sleep(interval_seconds)
                    
                except Exception as e:
                    logger.error(f"监控循环出错: {e}")
                    time.sleep(interval_seconds)
        
        self.monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info(f"启动监控，检查间隔: {interval_seconds}秒")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("监控已停止")
    
    def record_metric(self, metric_name: str, value: float, 
                     tags: Optional[Dict[str, str]] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """记录指标"""
        datapoint = MetricDataPoint(
            timestamp=time.time(),
            metric_name=metric_name,
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        self.metric_store.add_datapoint(datapoint)
    
    def start_crawl(self, site_id: str, url: str):
        """开始爬取监控"""
        logger.info(f"开始爬取监控: {site_id} ({url})")
        
        # 记录爬取开始时间
        self.record_metric("crawl.start_time", time.time(), tags={"site_id": site_id, "url": url})
        
        # 重置相关指标
        self.record_metric("crawl.requests.total", 0, tags={"site_id": site_id})
        self.record_metric("crawl.requests.success", 0, tags={"site_id": site_id})
        self.record_metric("crawl.requests.failed", 0, tags={"site_id": site_id})
        self.record_metric("crawl.pages.crawled", 0, tags={"site_id": site_id})
        
        # 记录活动爬取
        if not hasattr(self, 'active_crawls'):
            self.active_crawls = {}
        self.active_crawls[site_id] = {
            'start_time': time.time(),
            'url': url,
            'pages_crawled': 0,
            'jobs_found': 0
        }
    
    def end_crawl(self, site_id: str, pages_crawled: int, jobs_found: int, 
                  success: bool = True, error: Optional[str] = None):
        """结束爬取监控"""
        logger.info(f"结束爬取监控: {site_id} - 爬取 {pages_crawled} 页，找到 {jobs_found} 个职位，成功: {success}")
        
        # 记录爬取结束时间
        end_time = time.time()
        self.record_metric("crawl.end_time", end_time, tags={"site_id": site_id})
        
        # 计算爬取时长
        if hasattr(self, 'active_crawls') and site_id in self.active_crawls:
            start_time = self.active_crawls[site_id]['start_time']
            duration = end_time - start_time
            self.record_metric("crawl.duration_seconds", duration, tags={"site_id": site_id})
            
            # 清理活动爬取记录
            del self.active_crawls[site_id]
        
        # 记录最终结果
        self.record_metric("crawl.pages.crawled", pages_crawled, tags={"site_id": site_id})
        self.record_metric("crawl.jobs.found", jobs_found, tags={"site_id": site_id})
        self.record_metric("crawl.success", 1 if success else 0, tags={"site_id": site_id})
        
        if error:
            self.record_error("crawl_failure", count=1, url=site_id)
            self.record_metric("crawl.error", 1, tags={"site_id": site_id, "error": error[:100]})
    
    def record_crawl_metrics(self, total_crawled: int, successful: int, failed: int,
                            avg_response_time: float, requests_per_second: float,
                            depth: int, pages_discovered: int):
        """记录爬取指标"""
        current_time = time.time()
        
        # 计算成功率
        success_rate = successful / total_crawled if total_crawled > 0 else 0.0
        
        # 记录指标
        self.record_metric("crawl.requests.total", total_crawled)
        self.record_metric("crawl.requests.success", successful)
        self.record_metric("crawl.requests.failed", failed)
        self.record_metric("crawl.success_rate", success_rate)
        self.record_metric("crawl.response_time.avg", avg_response_time)
        self.record_metric("crawl.requests.per_second", requests_per_second)
        self.record_metric("crawl.depth.current", depth)
        self.record_metric("crawl.pages.crawled", total_crawled)
        self.record_metric("crawl.pages.discovered", pages_discovered)
        
        # 计算进度（如果有总页面数）
        if pages_discovered > 0:
            progress = total_crawled / pages_discovered if pages_discovered > 0 else 0.0
            self.record_metric("progress.percentage", min(1.0, progress))
    
    def record_error(self, error_type: str, count: int = 1, url: Optional[str] = None):
        """记录错误"""
        tags = {"error_type": error_type}
        if url:
            tags["url"] = url
        
        self.record_metric(f"errors.{error_type}", count, tags=tags)
    
    def record_system_metrics(self):
        """记录系统指标"""
        import psutil
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.record_metric("system.cpu.percent", cpu_percent)
        
        # 内存使用
        memory = psutil.virtual_memory()
        self.record_metric("system.memory.percent", memory.percent)
        self.record_metric("system.memory.used_mb", memory.used / 1024 / 1024)
        
        # 磁盘使用（如果有）
        try:
            disk = psutil.disk_usage('/')
            self.record_metric("system.disk.used_percent", disk.percent)
        except:
            pass
    
    def _check_alerts(self):
        """检查警报"""
        current_time = time.time()
        
        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if rule_id in self.alert_cooldown:
                if current_time - self.alert_cooldown[rule_id] < rule.cooldown_seconds:
                    continue
            
            # 获取相关指标数据
            datapoints = self.metric_store.get_metric_data(
                rule.metric_name,
                tags=rule.tags_filter,
                start_time=current_time - rule.duration_seconds,
                end_time=current_time
            )
            
            if not datapoints:
                continue
            
            # 检查最新的数据点
            latest_datapoint = datapoints[-1]
            
            # 获取最近的值用于匹配
            recent_values = [dp.value for dp in datapoints[-10:]]  # 最近10个值
            
            if rule.matches(latest_datapoint, recent_values):
                # 触发警报
                self._trigger_alert(rule, latest_datapoint)
                self.alert_cooldown[rule_id] = current_time
    
    def _trigger_alert(self, rule: AlertRule, datapoint: MetricDataPoint):
        """触发警报"""
        alert_id = f"alert_{int(time.time())}_{rule.rule_id}"
        
        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            timestamp=time.time(),
            severity=rule.severity,
            message=rule.get_alert_message(datapoint),
            metric_value=datapoint.value,
            metric_tags=datapoint.tags
        )
        
        self.alerts[alert_id] = alert
        
        # 发送通知
        self._send_notifications(alert)
        
        logger.warning(f"触发警报: {alert.message}")
    
    def _send_notifications(self, alert: Alert):
        """发送通知"""
        for channel in self.notification_channels.values():
            channel.send_notification(alert)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system"):
        """确认警报"""
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = time.time()
    
    def resolve_alert(self, alert_id: str):
        """解决警报"""
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = time.time()
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃警报（未解决）"""
        return [alert for alert in self.alerts.values() if not alert.resolved]
    
    def get_recent_alerts(self, limit: int = 50) -> List[Alert]:
        """获取最近警报"""
        alerts = sorted(self.alerts.values(), key=lambda x: x.timestamp, reverse=True)
        return alerts[:limit]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        current_time = time.time()
        
        # 获取关键指标
        crawl_stats = self.metric_store.get_metric_stats("crawl.success_rate", time_window_seconds=300)
        response_stats = self.metric_store.get_metric_stats("crawl.response_time.avg", time_window_seconds=300)
        request_stats = self.metric_store.get_metric_stats("crawl.requests.per_second", time_window_seconds=60)
        
        # 获取系统指标
        system_stats = {
            'cpu': self.metric_store.get_metric_stats("system.cpu.percent", time_window_seconds=60),
            'memory': self.metric_store.get_metric_stats("system.memory.percent", time_window_seconds=60)
        }
        
        # 获取错误统计
        error_stats = {}
        for error_type in ['network', 'timeout', 'http.4xx', 'http.5xx']:
            stats = self.metric_store.get_metric_stats(f"errors.{error_type}", time_window_seconds=300)
            error_stats[error_type] = stats
        
        # 获取活跃警报
        active_alerts = self.get_active_alerts()
        
        # 计算总体状态
        overall_status = "healthy"
        if any(a.severity == "critical" for a in active_alerts):
            overall_status = "critical"
        elif any(a.severity == "error" for a in active_alerts):
            overall_status = "error"
        elif any(a.severity == "warning" for a in active_alerts):
            overall_status = "warning"
        
        dashboard = {
            'timestamp': current_time,
            'overall_status': overall_status,
            'crawl_metrics': {
                'success_rate': crawl_stats.get('latest_value', 0),
                'avg_response_time': response_stats.get('latest_value', 0),
                'requests_per_second': request_stats.get('latest_value', 0),
                'total_crawled': self.metric_store.get_metric_stats("crawl.requests.total").get('latest_value', 0)
            },
            'system_metrics': system_stats,
            'error_metrics': error_stats,
            'alerts': {
                'active_count': len(active_alerts),
                'active_alerts': [a.to_dict() for a in active_alerts[:10]],  # 最多10个
                'recent_count': len(self.get_recent_alerts(100))
            },
            'monitoring_active': self.monitoring_active,
            'metric_count': len(self.metric_store.get_all_metrics())
        }
        
        return dashboard
    
    def get_metric_history(self, metric_name: str, tags: Optional[Dict[str, str]] = None,
                          time_window_seconds: int = 3600) -> Dict[str, Any]:
        """获取指标历史数据"""
        datapoints = self.metric_store.get_metric_data(
            metric_name,
            tags=tags,
            start_time=time.time() - time_window_seconds
        )
        
        # 转换为时间序列格式
        timestamps = []
        values = []
        
        for dp in datapoints:
            timestamps.append(dp.timestamp)
            values.append(dp.value)
        
        stats = self.metric_store.get_metric_stats(metric_name, tags, time_window_seconds)
        
        return {
            'metric_name': metric_name,
            'tags': tags or {},
            'time_window_seconds': time_window_seconds,
            'data_points': len(datapoints),
            'timestamps': timestamps,
            'values': values,
            'stats': stats
        }
    
    def export_report(self, output_file: str):
        """导出报告"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'dashboard': self.get_dashboard_data(),
                'metrics_summary': {},
                'alerts_summary': {
                    'total_alerts': len(self.alerts),
                    'active_alerts': len(self.get_active_alerts()),
                    'by_severity': defaultdict(int)
                }
            }
            
            # 按严重程度统计警报
            for alert in self.alerts.values():
                report['alerts_summary']['by_severity'][alert.severity] += 1
            
            # 指标摘要
            for metric_name in self.METRICS.keys():
                stats = self.metric_store.get_metric_stats(metric_name, time_window_seconds=3600)
                if stats['count'] > 0:
                    report['metrics_summary'][metric_name] = {
                        'description': self.METRICS[metric_name],
                        'latest_value': stats['latest_value'],
                        'average': stats['avg']
                    }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"导出监控报告到: {output_file}")
            
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
    
    def add_custom_alert_rule(self, rule: AlertRule):
        """添加自定义警报规则"""
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"添加自定义警报规则: {rule.name}")
    
    def remove_alert_rule(self, rule_id: str):
        """移除警报规则"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"移除警报规则: {rule_id}")
    
    def add_notification_channel(self, channel: NotificationChannel):
        """添加通知渠道"""
        self.notification_channels[channel.channel_id] = channel
        logger.info(f"添加通知渠道: {channel.name} ({channel.channel_type})")
    
    def remove_notification_channel(self, channel_id: str):
        """移除通知渠道"""
        if channel_id in self.notification_channels:
            del self.notification_channels[channel_id]
            logger.info(f"移除通知渠道: {channel_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'monitoring_active': self.monitoring_active,
            'metric_count': len(self.metric_store.get_all_metrics()),
            'datapoint_count': sum(len(q) for q in self.metric_store.metrics.values()),
            'alert_rule_count': len(self.alert_rules),
            'notification_channel_count': len(self.notification_channels),
            'active_alert_count': len(self.get_active_alerts()),
            'uptime': getattr(self, '_start_time', time.time()) if hasattr(self, '_start_time') else 0
        }