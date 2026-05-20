"""
深度爬取系统 - 获取网站所有相关内容
三个阶段完整实现：
1. 基础深层爬取核心引擎
2. 智能优化（机器学习、自适应策略）
3. 生产部署（性能调优、监控）
"""

__version__ = "1.0.0"
__author__ = "Chenney's AI Assistant"

# 核心组件
from .website_deep_crawler import WebsiteDeepCrawler, DeepCrawlConfig
from .link_discovery_engine import LinkDiscoveryEngine, LinkExtractor
from .sitemap_analyzer import SitemapAnalyzer
from .content_classifier import ContentClassifier

# 智能优化组件
try:
    from .ml_content_classifier import MLContentClassifier
    from .adaptive_crawler import AdaptiveCrawler
    from .anti_anti_crawler import AntiAntiCrawler
except ImportError:
    pass

# 生产部署组件
try:
    from .performance_optimizer import PerformanceOptimizer
    from .monitoring_system import DeepCrawlMonitor
    from .integration_adapter import DeepCrawlIntegrationAdapter
except ImportError:
    pass

# 工厂函数
def create_deep_crawler(config=None):
    """创建深度爬取器工厂函数"""
    from .website_deep_crawler import WebsiteDeepCrawler
    return WebsiteDeepCrawler(config)

__all__ = [
    # 核心
    'WebsiteDeepCrawler',
    'DeepCrawlConfig',
    'LinkDiscoveryEngine', 
    'LinkExtractor',
    'SitemapAnalyzer',
    'ContentClassifier',
    
    # 工厂函数
    'create_deep_crawler'
]