#!/usr/bin/env python3
"""
简化版深度爬取适配器 - 不依赖psutil或lxml
用于依赖问题无法解决时的回退方案
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class SimpleDeepCrawlAdapter:
    """简化版深度爬取适配器"""
    
    def __init__(self, deep_crawl_enabled: bool = True):
        self.deep_crawl_enabled = deep_crawl_enabled
        logger.info("📝 使用简化版深度爬取适配器（无psutil/lxml依赖）")
    
    async def deep_fetch_website(self, site_id: str, site_config: dict) -> list:
        """
        简化版深度爬取
        
        Args:
            site_id: 网站ID
            site_config: 网站配置
            
        Returns:
            职位列表
        """
        if not self.deep_crawl_enabled:
            return []
        
        logger.info(f"🌐 简化版深度爬取: {site_id}")
        
        # 模拟深度爬取结果
        return [
            {
                'title': f'简化版深度爬取职位 1 - {site_id}',
                'url': f'https://example.com/job/1',
                'content': f'这是通过简化版深度爬取找到的职位，来自{site_id}',
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', site_id),
                'simulated': True
            },
            {
                'title': f'简化版深度爬取职位 2 - {site_id}',
                'url': f'https://example.com/job/2',
                'content': f'这是另一个通过简化版深度爬取找到的职位，来自{site_id}',
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', site_id),
                'simulated': True
            }
        ]
    
    def get_crawl_statistics(self) -> dict:
        """获取爬取统计信息"""
        return {
            "adapter_type": "simple",
            "deep_crawl_enabled": self.deep_crawl_enabled,
            "simulated_mode": True,
            "message": "使用简化版适配器（无psutil/lxml依赖）"
        }

# 导出
__all__ = ['SimpleDeepCrawlAdapter']
