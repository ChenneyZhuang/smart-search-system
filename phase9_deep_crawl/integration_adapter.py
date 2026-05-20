#!/usr/bin/env python3
"""
深度爬取集成适配器 - 将深度爬取系统与现有岗位扫描器集成
支持智能策略选择、向后兼容和性能监控
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import sys
import os

# 添加本地模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from website_deep_crawler import WebsiteDeepCrawler, DeepCrawlConfig
from link_discovery_engine import LinkDiscoveryEngine
from content_classifier import ContentClassifier
from performance_optimizer import PerformanceOptimizer
from monitoring_system import DeepCrawlMonitor

logger = logging.getLogger(__name__)

class DeepCrawlIntegrationAdapter:
    """深度爬取集成适配器 - 连接深度爬取系统和岗位扫描器"""
    
    def __init__(self, deep_crawl_enabled: bool = True, config_dir: Optional[str] = None):
        """
        初始化适配器
        
        Args:
            deep_crawl_enabled: 是否启用深度爬取
            config_dir: 配置文件目录
        """
        self.deep_crawl_enabled = deep_crawl_enabled
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / "config"
        
        # 深度爬取组件
        self.deep_crawler = None
        self.link_discovery = None
        self.content_classifier = None
        self.performance_optimizer = None
        self.monitor = None
        
        # 网站特定配置
        self.website_configs = {}
        
        if deep_crawl_enabled:
            self.init_components()
            self.load_configurations()
    
    def init_components(self):
        """初始化深度爬取组件"""
        try:
            # 深度爬取配置 - 使用优化后的值，避免超时
            deep_config = DeepCrawlConfig(
                max_depth=2,           # 减少深度，避免无限递归
                max_pages=15,          # 减少每站页面数，避免超时
                max_concurrent=3,      # 减少并发数，降低服务器压力
                request_timeout=45.0,  # 增加单请求超时
                respect_robots=True,
                enable_sitemap=True,
                crawl_detail_pages=True
            )
            
            self.deep_crawler = WebsiteDeepCrawler(deep_config)
            self.link_discovery = LinkDiscoveryEngine()
            self.content_classifier = ContentClassifier()
            self.performance_optimizer = PerformanceOptimizer()
            self.monitor = DeepCrawlMonitor()
            
            logger.info("✅ 深度爬取组件初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 深度爬取组件初始化失败: {e}")
            self.deep_crawl_enabled = False
    
    def load_configurations(self):
        """加载网站特定配置"""
        config_files = [
            self.config_dir / "job_websites.json",
            self.config_dir / "deep_crawl_defaults.json",
            self.config_dir / "website_strategies.json"
        ]
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    if config_file.name == "job_websites.json":
                        self.website_configs.update(config.get("websites", {}))
                    elif config_file.name == "deep_crawl_defaults.json":
                        # 合并默认配置
                        for site_id, site_config in config.items():
                            if site_id not in self.website_configs:
                                self.website_configs[site_id] = site_config
                    
                    logger.info(f"✅ 加载配置文件: {config_file.name}")
                    
                except Exception as e:
                    logger.warning(f"⚠️  配置文件加载失败 {config_file.name}: {e}")
        
        # 设置默认配置
        if not self.website_configs:
            self.website_configs = self.get_default_website_configs()
            logger.info("📝 使用默认网站配置")
    
    def get_default_website_configs(self) -> Dict[str, Dict]:
        """获取默认网站配置"""
        return {
            "indeed_canberra_analyst": {
                "name": "Indeed - Data Analyst Canberra",
                "url": "https://au.indeed.com/jobs?q=data+analyst&l=Canberra+ACT",
                "type": "dynamic",
                "difficulty": "medium",
                "allow_deep_crawl": True,
                "deep_crawl_config": {
                    "max_pages": 20,
                    "max_depth": 3,
                    "crawl_detail_pages": True,
                    "site_type": "indeed",
                    "pagination_patterns": ["start={}", "page={}", "&p={}"],
                    "job_detail_selectors": [".jcs-JobTitle", "a[data-jk]"],
                    "list_page_selectors": [".job_seen_beacon"],
                    "ignore_patterns": ["login", "signup", "employer"]
                }
            },
            "seek_canberra_analyst": {
                "name": "Seek - Data Analyst Canberra",
                "url": "https://www.seek.com.au/data-analyst-jobs/in-All-Canberra-ACT",
                "type": "dynamic",
                "difficulty": "medium",
                "allow_deep_crawl": True,
                "deep_crawl_config": {
                    "max_pages": 15,
                    "max_depth": 2,
                    "crawl_detail_pages": True,
                    "site_type": "seek",
                    "pagination_patterns": ["page={}", "offset={}"],
                    "job_detail_selectors": ["[data-automation='jobTitle']"],
                    "list_page_selectors": ["[data-automation='normalJob']"],
                    "ignore_patterns": ["account", "profile", "login"]
                }
            },
            "aps_canberra_analyst": {
                "name": "APS Jobs - Data Analyst Canberra",
                "url": "https://www.apsjobs.gov.au/s/search-results?keywords=data+analyst&location=Canberra",
                "type": "static",
                "difficulty": "easy",
                "allow_deep_crawl": True,
                "deep_crawl_config": {
                    "max_pages": 10,
                    "max_depth": 2,
                    "crawl_detail_pages": True,
                    "site_type": "aps",
                    "pagination_patterns": ["start={}", "page={}"],
                    "job_detail_selectors": [".job-title", ".job-link"],
                    "list_page_selectors": [".search-result"],
                    "ignore_patterns": ["login", "register"]
                }
            }
        }
    
    async def deep_fetch_website(self, site_id: str, site_config: Dict) -> List[Dict]:
        """
        深度爬取网站
        
        Args:
            site_id: 网站ID
            site_config: 网站配置
            
        Returns:
            职位列表
        """
        if not self.deep_crawl_enabled or not self.deep_crawler:
            logger.warning(f"⚠️  深度爬取未启用，使用浅层爬取: {site_id}")
            return []
        
        # 检查是否允许深度爬取
        if not site_config.get('allow_deep_crawl', False):
            logger.info(f"📝 网站 {site_id} 不允许深度爬取，使用浅层爬取")
            return []
        
        url = site_config.get('url', '')
        name = site_config.get('name', site_id)
        deep_config = site_config.get('deep_crawl_config', {})
        
        if not url:
            logger.error(f"❌ 网站 {site_id} 无URL配置")
            return []
        
        logger.info(f"🌐 开始深度爬取: {name} ({url})")
        
        try:
            # 启动监控
            self.monitor.start_crawl(site_id, url)
            
            # 执行深度爬取
            # 首先检查是否需要基于网站配置创建新的爬取器实例
            if deep_config:
                # 创建网站特定配置的爬取器
                site_specific_config = DeepCrawlConfig(
                    max_depth=deep_config.get('max_depth', 3),
                    max_pages=deep_config.get('max_pages', 20),
                    max_concurrent=self.deep_crawler.config.max_concurrent,
                    request_timeout=self.deep_crawler.config.request_timeout,
                    respect_robots=self.deep_crawler.config.respect_robots,
                    enable_sitemap=self.deep_crawler.config.enable_sitemap,
                    crawl_detail_pages=self.deep_crawler.config.crawl_detail_pages
                )
                # 创建临时爬取器实例
                site_crawler = WebsiteDeepCrawler(site_specific_config)
                await site_crawler.start()
                results = await site_crawler.deep_crawl(start_url=url)
                await site_crawler.close()
            else:
                # 使用默认爬取器
                results = await self.deep_crawler.deep_crawl(start_url=url)
            
            # 处理爬取结果
            jobs = self.process_crawl_results(results, site_config)
            
            # 更新监控
            self.monitor.end_crawl(
                site_id=site_id,
                pages_crawled=len(results.get('pages', [])),
                jobs_found=len(jobs),
                success=True
            )
            
            logger.info(f"✅ 深度爬取完成: {name} - 找到 {len(jobs)} 个职位")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ 深度爬取失败 {name}: {e}")
            
            # 更新监控为失败
            if self.monitor:
                self.monitor.end_crawl(
                    site_id=site_id,
                    pages_crawled=0,
                    jobs_found=0,
                    success=False,
                    error=str(e)
                )
            
            return []
    
    def process_crawl_results(self, results: Dict, site_config: Dict) -> List[Dict]:
        """
        处理深度爬取结果，提取职位信息
        
        Args:
            results: 爬取结果
            site_config: 网站配置
            
        Returns:
            职位列表
        """
        jobs = []
        deep_config = site_config.get('deep_crawl_config', {})
        
        # 方法1: 处理potential_jobs（深度爬取器已识别的职位）
        potential_jobs = results.get('potential_jobs', [])
        for job_data in potential_jobs:
            job = self.extract_job_from_potential(job_data, site_config)
            if job:
                jobs.append(job)
        
        # 方法2: 从pages_by_type中提取detail页面（如果potential_jobs为空）
        if not jobs:
            for page_type, pages in results.get('pages_by_type', {}).items():
                if page_type == 'detail' and pages:
                    for page in pages:
                        job = self.extract_job_from_page(page, site_config)
                        if job:
                            jobs.append(job)
        
        # 方法3: 处理原始pages数组（向后兼容）
        if not jobs:
            for page in results.get('pages', []):
                # 跳过非职位详情页
                if page.get('page_type') != 'detail':
                    continue
                
                # 提取职位信息
                job = self.extract_job_from_page(page, site_config)
                if job:
                    jobs.append(job)
        
        # 去重（基于URL或标题）
        unique_jobs = self.deduplicate_jobs(jobs)
        
        logger.info(f"从深度爬取结果中提取到 {len(unique_jobs)} 个职位")
        return unique_jobs
    
    def extract_job_from_potential(self, job_data: Dict, site_config: Dict) -> Optional[Dict]:
        """
        从potential_jobs数据中提取职位信息
        
        Args:
            job_data: 潜在职位数据
            site_config: 网站配置
            
        Returns:
            职位信息字典或None
        """
        try:
            # 基础信息
            job = {
                'url': job_data.get('url', ''),
                'title': job_data.get('title', ''),
                'content': job_data.get('content', ''),
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', ''),
                'company': self._extract_company_from_url(job_data.get('url', '')),
                'location': self._extract_location_from_content(job_data.get('content', ''))
            }
            
            # 提取薪资信息
            content = job_data.get('content', '')
            salary = self._extract_salary_from_content(content)
            if salary:
                job['salary'] = salary
            
            return job
            
        except Exception as e:
            logger.warning(f"⚠️  从potential_job提取职位信息失败: {e}")
            return None
    
    def extract_job_from_page(self, page: Dict, site_config: Dict) -> Optional[Dict]:
        """
        从页面数据中提取职位信息 - 增强版，支持网站专用解析
        
        Args:
            page: 页面数据
            site_config: 网站配置
            
        Returns:
            职位信息字典或None
        """
        try:
            url = page.get('url', '')
            title = page.get('title', '')
            content = page.get('content_text', '')
            html = page.get('html', '')
            
            # 基础信息
            job = {
                'url': url,
                'title': title,
                'content': content,
                'html': html[:1000],  # 只存储前1000字符
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', ''),
                'company': self._extract_company_from_url(url),
                'location': self._extract_location_from_content(content)
            }
            
            # 网站专用解析
            if 'indeed.com' in url:
                # Indeed专用解析
                job = self._extract_indeed_job(job, page, site_config)
            elif 'seek.com.au' in url:
                # Seek专用解析
                job = self._extract_seek_job(job, page, site_config)
            elif 'apsjobs.gov.au' in url:
                # APS Jobs专用解析
                job = self._extract_aps_job(job, page, site_config)
            elif 'anu.edu.au' in url:
                # ANU专用解析
                job = self._extract_anu_job(job, page, site_config)
            elif 'csiro.au' in url:
                # CSIRO专用解析
                job = self._extract_csiro_job(job, page, site_config)
            else:
                # 通用解析
                job = self._extract_generic_job(job, page, site_config)
            
            # 如果标题太短或无意义，尝试改进
            if not job.get('title') or len(job['title']) < 5 or job['title'].lower() in ['search page', 'jobs', 'careers']:
                improved_title = self._improve_job_title(job, url, content)
                if improved_title:
                    job['title'] = improved_title
            
            return job
            
        except Exception as e:
            logger.warning(f"⚠️  职位信息提取失败: {e}")
            return None
    
    def _extract_company_from_url(self, url: str) -> str:
        """从URL中提取公司名称"""
        if 'indeed.com' in url:
            return 'Indeed Listing'
        elif 'seek.com.au' in url:
            return 'Seek Listing'
        elif 'apsjobs.gov.au' in url:
            return 'Australian Government'
        elif 'anu.edu.au' in url:
            return 'Australian National University'
        elif 'csiro.au' in url:
            return 'CSIRO'
        else:
            # 尝试从域名提取
            import re
            match = re.search(r'://(?:www\.)?([^/]+)', url)
            if match:
                domain = match.group(1)
                # 移除常见后缀
                domain = domain.replace('.com', '').replace('.com.au', '').replace('.org', '').replace('.gov', '').replace('.edu', '')
                return domain.title()
            return 'Unknown'
    
    def _extract_location_from_content(self, content: str) -> str:
        """从内容中提取地点"""
        import re
        location_patterns = [
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'location[:\\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'based\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Canberra',
            r'Sydney',
            r'Melbourne',
            r'Brisbane',
            r'Perth',
            r'Adelaide'
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return matches[0] if isinstance(matches[0], str) else matches[0][0]
        
        return 'Location not specified'
    
    def _extract_salary_from_content(self, content: str) -> str:
        """从内容中提取薪资信息"""
        import re
        salary_patterns = [
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:-\s*\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)?',
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:per\s+year|per\s+annum|p\.a\.)',
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:per\s+hour|per\s+hr)'
        ]
        
        for pattern in salary_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return ''
    
    def _extract_indeed_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """Indeed专用职位解析 - 增强版，支持Cloudflare拦截页面"""
        url = job.get('url', '')
        content = job.get('content', '')
        html = page.get('html', '')
        
        # 检测Cloudflare或访问限制
        is_blocked = False
        block_indicators = [
            'Cloudflare',
            'cf-',
            'challenge-form',
            'Checking your browser',
            'Access denied',
            'bot detection',
            'security check',
            'Please enable JavaScript'
        ]
        
        for indicator in block_indicators:
            if indicator in content.lower() or indicator in html.lower():
                is_blocked = True
                break
        
        if is_blocked:
            # 网站被拦截，尝试从有限信息中提取
            job['access_blocked'] = True
            job['notes'] = '网站有访问限制，需要浏览器自动化'
            
            # 从URL提取尽可能多的信息
            if 'indeed.com' in url:
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                query = urllib.parse.parse_qs(parsed.query)
                
                # 提取职位ID
                if 'jk' in query:
                    job_id = query['jk'][0]
                    job['job_id'] = job_id
                    if not job.get('title') or job['title'] in ['Indeed', 'Search Page']:
                        job['title'] = f'Indeed Job #{job_id}'
                
                # 提取搜索关键词
                if 'q' in query:
                    search_query = query['q'][0]
                    job['search_query'] = search_query
                    if not job.get('title') or len(job['title']) < 10:
                        job['title'] = f'Indeed: {search_query.replace("+", " ").title()}'
                
                # 提取地点
                if 'l' in query:
                    location = query['l'][0]
                    job['location'] = location.replace('+', ' ')
                
                # 提取日期范围
                if 'fromage' in query:
                    fromage = query['fromage'][0]
                    job['fromage_days'] = fromage
                    job['date_filter'] = f'Last {fromage} days'
        else:
            # 正常页面，执行标准提取
            job['access_blocked'] = False
            
            # 尝试从URL提取职位ID
            if 'jk=' in url:
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                query = urllib.parse.parse_qs(parsed.query)
                job_id = query.get('jk', [''])[0]
                if job_id:
                    job['job_id'] = job_id
            
            # Indeed特定字段提取
            if 'salary' not in job:
                # Indeed常见的薪资模式
                indeed_salary_patterns = [
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:a year|per year|per annum)',
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*an hour',
                    r'Estimated\s*:\s*\$[\d,]+(?:\.\d{2})?',
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:per\s+annum|p\.a\.)',
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:per\s+hour|p\.h\.)'
                ]
                
                for pattern in indeed_salary_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        job['salary'] = matches[0]
                        break
            
            # 提取职位类型
            employment_patterns = [
                (r'full[\s-]*time', 'Full-time'),
                (r'part[\s-]*time', 'Part-time'),
                (r'contract', 'Contract'),
                (r'permanent', 'Permanent'),
                (r'temporary', 'Temporary'),
                (r'casual', 'Casual')
            ]
            
            for pattern, emp_type in employment_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    job['employment_type'] = emp_type
                    break
            
            # 提取公司名称（如果可能）
            company_patterns = [
                r'company[\s:]+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)',
                r'employer[\s:]+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)',
                r'hiring[\s:]+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)'
            ]
            
            for pattern in company_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    job['company'] = matches[0]
                    break
        
        # 如果标题太短或无意义，尝试改进
        if not job.get('title') or len(job['title']) < 5 or job['title'].lower() in ['indeed', 'search page', 'jobs']:
            if url and 'indeed.com' in url:
                # 从URL生成更好的标题
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                
                if parsed.path.startswith('/viewjob'):
                    # 查看职位页面
                    if 'jk' in parsed.query:
                        job_id = parsed.query.split('jk=')[1].split('&')[0] if '&' in parsed.query else parsed.query.split('jk=')[1]
                        job['title'] = f'Indeed Job #{job_id}'
                elif parsed.path.startswith('/jobs'):
                    # 搜索页面
                    query_params = urllib.parse.parse_qs(parsed.query)
                    if 'q' in query_params:
                        search_query = query_params['q'][0]
                        job['title'] = f'Indeed Search: {search_query.replace("+", " ").title()}'
                    else:
                        job['title'] = 'Indeed Job Search'
        
        return job
    
    def _extract_seek_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """Seek专用职位解析"""
        url = job.get('url', '')
        content = job.get('content', '')
        title = job.get('title', '')
        
        # Seek特定的数据属性提取
        html = page.get('html', '')
        
        # 尝试提取data-automation属性
        import re
        
        # 提取薪资（Seek常见格式）
        seek_salary_patterns = [
            r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:p\.a\.|per annum)',
            r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:inc\. super|incl\. super)',
            r'Attractive\s+salary',
            r'Competitive\s+salary'
        ]
        
        for pattern in seek_salary_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                job['salary'] = matches[0]
                break
        
        # 提取工作类型
        work_type_patterns = [
            r'Full\s*[Tt]ime',
            r'Part\s*[Tt]ime',
            r'Contract',
            r'Permanent',
            r'Temporary'
        ]
        
        for pattern in work_type_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                job['employment_type'] = matches[0]
                break
        
        # 如果标题是通用的，尝试改进
        if title in ['Jobs at SEEK', 'Search Page', 'SEEK']:
            # 从URL提取信息
            if '/job/' in url:
                # 尝试从URL路径提取线索
                path_parts = url.split('/')
                if len(path_parts) > 1:
                    last_part = path_parts[-1]
                    if last_part and '?' not in last_part:
                        job['title'] = f'SEEK Position - {last_part}'
        
        return job
    
    def _extract_aps_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """APS Jobs专用职位解析 - 增强版，支持Cloudflare拦截页面"""
        url = job.get('url', '')
        content = job.get('content', '')
        title = job.get('title', '')
        html = page.get('html', '')
        
        # 检测Cloudflare拦截页面
        is_cloudflare_blocked = False
        cloudflare_indicators = [
            'Cloudflare',
            'cf-browser-verification',
            'challenge-form',
            'DDoS protection',
            'Checking your browser',
            'Sorry to interrupt',
            'CSS Error Refresh'
        ]
        
        for indicator in cloudflare_indicators:
            if indicator in content or indicator in html:
                is_cloudflare_blocked = True
                break
        
        if is_cloudflare_blocked:
            # Cloudflare拦截，尝试从有限信息中提取
            job['cloudflare_blocked'] = True
            job['notes'] = '网站受Cloudflare保护，需要浏览器自动化'
            
            # 尝试从URL提取信息
            if 'apsjobs.gov.au' in url:
                # 分析URL参数
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                query = urllib.parse.parse_qs(parsed.query)
                
                # 从查询参数提取职位类型
                if 'query' in query:
                    query_text = query['query'][0]
                    if query_text:
                        job['query'] = query_text
                        # 尝试从查询生成有意义的标题
                        if not job.get('title') or job['title'] in ['APS Jobs', 'Search Page']:
                            job['title'] = f'APS Jobs - {query_text.replace("+", " ").title()}'
                
                # 从路径提取信息
                path = parsed.path
                if '/job/' in path:
                    # 尝试提取职位ID
                    parts = path.split('/')
                    for i, part in enumerate(parts):
                        if part == 'job' and i + 1 < len(parts):
                            job_id = parts[i + 1]
                            if job_id.isdigit():
                                job['job_id'] = job_id
                                if not job.get('title'):
                                    job['title'] = f'APS Job #{job_id}'
                            break
        else:
            # 正常页面，执行标准提取
            job['cloudflare_blocked'] = False
            
            # APS Jobs特定提取
            if 'salary' not in job:
                # APS薪资范围常见格式
                aps_salary_patterns = [
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?',
                    r'APS\s*[1-6]',
                    r'EL\s*[1-2]',
                    r'Executive\s+Level',
                    r'SES\s*[1-3]',
                    r'Senior\s+Executive\s+Service'
                ]
                
                for pattern in aps_salary_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        if 'salary' not in job:
                            job['salary'] = matches[0]
                        if any(mark in matches[0] for mark in ['APS', 'EL', 'SES', 'Executive']):
                            job['classification'] = matches[0]
                        break
            
            # 提取部门信息
            dept_patterns = [
                r'Department\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Department',
                r'Agency\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Agency',
                r'Ministry\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            ]
            
            for pattern in dept_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    job['department'] = matches[0]
                    break
            
            # 提取职位类型
            job_type_patterns = [
                r'Ongoing',
                r'Non-ongoing',
                r'Temporary',
                r'Casual',
                r'Full-time',
                r'Part-time',
                r'Contract'
            ]
            
            for pattern in job_type_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    job['employment_type'] = pattern
                    break
        
        # 政府职位特定字段
        job['government'] = True
        job['sector'] = 'Public'
        
        # 如果标题太短或无意义，尝试改进
        if not job.get('title') or len(job['title']) < 5 or job['title'] in ['APS Jobs', 'Search Page', 'Home']:
            if url and 'apsjobs.gov.au' in url:
                # 从URL生成更好的标题
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                
                if parsed.path == '/s/search-results':
                    query = urllib.parse.parse_qs(parsed.query).get('query', [''])[0]
                    if query:
                        job['title'] = f'APS Jobs Search: {query.replace("+", " ").title()}'
                    else:
                        job['title'] = 'APS Jobs Search Results'
                elif parsed.path == '/':
                    job['title'] = 'APS Jobs Home'
                else:
                    # 从路径生成标题
                    path_parts = [p for p in parsed.path.split('/') if p]
                    if path_parts:
                        last_part = path_parts[-1]
                        if last_part:
                            job['title'] = f'APS {last_part.replace("-", " ").title()}'
        
        return job
    
    def _extract_anu_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """ANU专用职位解析"""
        content = job.get('content', '')
        
        # ANU特定字段
        job['sector'] = 'Education'
        job['institution'] = 'Australian National University'
        
        # 学术职位分类
        academic_patterns = [
            r'Lecturer',
            r'Senior\s+Lecturer',
            r'Associate\s+Professor',
            r'Professor',
            r'Research\s+Fellow',
            r'Postdoctoral'
        ]
        
        for pattern in academic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                job['academic_level'] = pattern.strip()
                break
        
        return job
    
    def _extract_csiro_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """CSIRO专用职位解析"""
        content = job.get('content', '')
        
        # CSIRO特定字段
        job['sector'] = 'Research'
        job['organization'] = 'CSIRO'
        
        # 研究领域
        research_patterns = [
            r'Data\s+Science',
            r'Research\s+Scientist',
            r'Principal\s+Research\s+Scientist',
            r'Senior\s+Research\s+Scientist'
        ]
        
        for pattern in research_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                job['research_area'] = pattern.strip()
                break
        
        return job
    
    def _extract_generic_job(self, job: Dict, page: Dict, site_config: Dict) -> Dict:
        """通用职位解析"""
        content = job.get('content', '')
        
        # 提取薪资（通用模式）
        if 'salary' not in job:
            salary = self._extract_salary_from_content(content)
            if salary:
                job['salary'] = salary
        
        # 提取地点（如果未设置）
        if job.get('location') == 'Location not specified':
            location = self._extract_location_from_content(content)
            if location != 'Location not specified':
                job['location'] = location
        
        # 提取其他常见信息
        employment_patterns = [
            (r'full[\s-]*time', 'Full-time'),
            (r'part[\s-]*time', 'Part-time'),
            (r'contract', 'Contract'),
            (r'permanent', 'Permanent'),
            (r'temporary', 'Temporary'),
            (r'casual', 'Casual')
        ]
        
        for pattern, employment_type in employment_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                job['employment_type'] = employment_type
                break
        
        return job
    
    def _improve_job_title(self, job: Dict, url: str, content: str) -> str:
        """改进职位标题"""
        current_title = job.get('title', '')
        
        # 如果标题太短或无意义
        if not current_title or len(current_title) < 5 or current_title.lower() in ['search page', 'jobs', 'careers', 'home']:
            # 尝试从URL提取
            if '/job/' in url:
                # 从URL路径提取职位ID或描述
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                path = parsed.path
                
                if '/job/' in path:
                    parts = path.split('/')
                    for i, part in enumerate(parts):
                        if part == 'job' and i + 1 < len(parts):
                            next_part = parts[i + 1]
                            if next_part and not next_part.isdigit():
                                return f'Position - {next_part.replace("-", " ").title()}'
                            elif next_part and next_part.isdigit():
                                return f'Job #{next_part}'
            
            # 尝试从内容提取
            if content:
                # 查找可能的职位标题模式
                title_patterns = [
                    r'<h1[^>]*>([^<]+)</h1>',
                    r'<title>([^<]+)</title>',
                    r'Position\s*:\s*([^\n]+)',
                    r'Role\s*:\s*([^\n]+)',
                    r'Job\s+Title\s*:\s*([^\n]+)'
                ]
                
                for pattern in title_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        candidate = matches[0].strip()
                        if len(candidate) > 10:  # 有意义的长度
                            return candidate[:100]  # 限制长度
            
            # 使用默认标题
            domain = 'Unknown'
            if 'indeed.com' in url:
                domain = 'Indeed'
            elif 'seek.com.au' in url:
                domain = 'SEEK'
            elif 'apsjobs.gov.au' in url:
                domain = 'APS Jobs'
            
            return f'{domain} Job Listing'
        
        return current_title
    
    def deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """职位去重"""
        unique_jobs = []
        seen_urls = set()
        seen_titles = set()
        
        for job in jobs:
            url = job.get('url', '')
            title = job.get('title', '')
            
            # 基于URL和标题的去重
            if url and url not in seen_urls:
                if title and title not in seen_titles:
                    unique_jobs.append(job)
                    seen_urls.add(url)
                    seen_titles.add(title)
                elif not title:
                    unique_jobs.append(job)
                    seen_urls.add(url)
        
        return unique_jobs
    
    def get_crawl_statistics(self) -> Dict:
        """获取爬取统计信息"""
        if not self.monitor:
            return {}
        
        return self.monitor.get_statistics()
    
    def save_configuration(self, config_file: str = "job_websites.json"):
        """保存网站配置"""
        try:
            config_path = self.config_dir / config_file
            
            # 确保目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            config_data = {
                "websites": self.website_configs,
                "updated_at": datetime.now().isoformat(),
                "version": "1.0.0"
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 配置保存成功: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 配置保存失败: {e}")
            return False

# 导入正则表达式
import re

# 简化版本用于快速测试
class SimpleDeepCrawlAdapter:
    """简化版深度爬取适配器 - 用于快速集成测试"""
    
    def __init__(self, deep_crawl_enabled: bool = True):
        self.deep_crawl_enabled = deep_crawl_enabled
    
    async def deep_fetch_website(self, site_id: str, site_config: Dict) -> List[Dict]:
        """简化版深度爬取"""
        if not self.deep_crawl_enabled:
            return []
        
        # 模拟深度爬取结果
        return [
            {
                'title': f'深度爬取职位 1 - {site_id}',
                'url': f'https://example.com/job/1',
                'content': f'这是通过深度爬取找到的职位信息，来自{site_id}',
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', site_id)
            },
            {
                'title': f'深度爬取职位 2 - {site_id}',
                'url': f'https://example.com/job/2',
                'content': f'这是通过深度爬取找到的另一个职位，来自{site_id}',
                'crawled_at': datetime.now().isoformat(),
                'source': site_config.get('name', site_id)
            }
        ]

# 异步测试函数
async def test_deep_crawl_adapter():
    """测试深度爬取适配器"""
    adapter = DeepCrawlIntegrationAdapter(deep_crawl_enabled=True)
    
    # 测试Indeed配置
    site_config = {
        'name': 'Indeed - Data Analyst Canberra',
        'url': 'https://au.indeed.com/jobs?q=data+analyst&l=Canberra+ACT',
        'allow_deep_crawl': True,
        'deep_crawl_config': {
            'max_pages': 5,
            'max_depth': 2,
            'site_type': 'indeed'
        }
    }
    
    jobs = await adapter.deep_fetch_website('indeed_test', site_config)
    print(f"找到 {len(jobs)} 个职位")
    
    return jobs

if __name__ == "__main__":
    # 简单测试
    logging.basicConfig(level=logging.INFO)
    
    asyncio.run(test_deep_crawl_adapter())