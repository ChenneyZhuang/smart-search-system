#!/usr/bin/env python3
"""
网站深度爬取器 - 核心引擎
获取网站所有相关内容，支持并发爬取、智能链接发现和内容分类
"""

import asyncio
import aiohttp
import hashlib
import logging
import json
import time
import urllib.robotparser
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
import re
import random
from collections import defaultdict
import sys
import os

# 添加本地模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

logger = logging.getLogger(__name__)

@dataclass
class DeepCrawlConfig:
    """深度爬取配置"""
    max_depth: int = 3                     # 最大爬取深度
    max_pages: int = 100                   # 最大页面数
    max_concurrent: int = 5                # 最大并发数
    request_timeout: float = 30.0          # 请求超时时间
    request_delay_min: float = 1.0         # 最小请求延迟
    request_delay_max: float = 3.0         # 最大请求延迟
    respect_robots: bool = True            # 尊重robots.txt
    enable_sitemap: bool = True            # 启用网站地图分析
    follow_external_links: bool = False    # 是否跟踪外部链接
    crawl_detail_pages: bool = True        # 是否爬取详情页
    enable_caching: bool = True            # 启用缓存
    user_agent_rotation: bool = True       # User-Agent轮换
    random_delay: bool = True              # 随机延迟
    
    # 内容过滤
    min_content_length: int = 100          # 最小内容长度
    max_content_similarity: float = 0.8    # 最大内容相似度（超过则去重）
    
    # 输出选项
    save_html: bool = False                # 保存HTML内容
    save_text: bool = True                 # 保存文本内容
    output_dir: str = "./deep_crawl_output" # 输出目录
    
    def __post_init__(self):
        # 确保配置合理
        if self.max_depth < 1:
            self.max_depth = 1
        if self.max_pages < 1:
            self.max_pages = 10
        if self.max_concurrent < 1:
            self.max_concurrent = 1
        elif self.max_concurrent > 20:
            self.max_concurrent = 20

@dataclass
class CrawledPage:
    """爬取的页面信息"""
    url: str
    depth: int
    status_code: int
    content_type: str = ""
    title: str = ""
    content_text: str = ""
    html: str = ""
    links_found: List[str] = field(default_factory=list)
    page_type: str = "unknown"  # list, detail, form, other
    crawled_at: float = field(default_factory=time.time)
    error: str = ""
    
    @property
    def is_successful(self):
        return self.status_code == 200
    
    @property
    def content_hash(self):
        """内容哈希值，用于去重"""
        if self.content_text:
            return hashlib.md5(self.content_text.encode()).hexdigest()
        return hashlib.md5(self.html.encode()).hexdigest() if self.html else ""

class WebsiteDeepCrawler:
    """网站深度爬取器"""
    
    def __init__(self, config: Optional[DeepCrawlConfig] = None):
        self.config = config or DeepCrawlConfig()
        
        # 爬取状态
        self.crawled_urls: Dict[str, CrawledPage] = {}  # URL -> 页面信息
        self.discovered_urls: Set[str] = set()          # 已发现待爬取的URL
        self.robots_parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self.domain_info: Dict[str, Dict] = {}          # 域名信息
        
        # 统计信息
        self.stats = {
            'total_crawled': 0,
            'successful': 0,
            'failed': 0,
            'total_links_found': 0,
            'unique_domains': set(),
            'start_time': time.time(),
            'end_time': None
        }
        
        # User-Agent列表
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Edge/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
        ]
        
        # 会话和连接池
        self.session: Optional[aiohttp.ClientSession] = None
        self.connector: Optional[aiohttp.TCPConnector] = None
        
        # 创建输出目录
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"深度爬取器初始化完成，配置: {self.config}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def start(self):
        """启动爬取器，创建会话"""
        self.connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent * 2,
            limit_per_host=self.config.max_concurrent,
            ttl_dns_cache=300
        )
        
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
        )
        
        logger.info(f"爬取会话已启动，最大并发: {self.config.max_concurrent}")
    
    async def close(self):
        """关闭爬取器"""
        if self.session:
            await self.session.close()
            self.session = None
        
        if self.connector:
            await self.connector.close()
            self.connector = None
        
        self.stats['end_time'] = time.time()
        logger.info(f"爬取会话已关闭")
    
    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        if self.config.user_agent_rotation:
            return random.choice(self.user_agents)
        return self.user_agents[0]
    
    async def get_robots_parser(self, url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        """获取robots.txt解析器"""
        parsed = urllib.parse.urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        if domain in self.robots_parsers:
            return self.robots_parsers[domain]
        
        if not self.config.respect_robots:
            return None
        
        try:
            robots_url = f"{domain}/robots.txt"
            async with self.session.get(robots_url, timeout=10) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(robots_content.splitlines())
                    self.robots_parsers[domain] = parser
                    return parser
        except Exception as e:
            logger.debug(f"无法获取robots.txt: {e}")
        
        return None
    
    def can_fetch(self, url: str) -> bool:
        """检查是否允许爬取该URL"""
        if not self.config.respect_robots:
            return True
        
        parser = self.robots_parsers.get(self.get_domain(url))
        if parser:
            return parser.can_fetch(self.get_random_user_agent(), url)
        
        return True
    
    def get_domain(self, url: str) -> str:
        """获取URL的域名"""
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def normalize_url(self, url: str, base_url: str) -> str:
        """规范化URL"""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # 如果是相对URL
            if not parsed.scheme:
                url = urllib.parse.urljoin(base_url, url)
                parsed = urllib.parse.urlparse(url)
            
            # 标准化URL
            normalized = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # 忽略fragment
            ))
            
            # 移除尾部斜杠（除非是根路径）
            if normalized.endswith('/') and len(parsed.path) > 1:
                normalized = normalized.rstrip('/')
            
            return normalized
        except Exception as e:
            logger.warning(f"URL规范化失败 {url}: {e}")
            return url
    
    def should_crawl_url(self, url: str, current_depth: int) -> bool:
        """判断是否应该爬取该URL"""
        # 检查深度限制
        if current_depth >= self.config.max_depth:
            logger.debug(f"跳过URL（深度限制）: {url}")
            return False
        
        # 检查已爬取
        if url in self.crawled_urls:
            logger.debug(f"跳过URL（已爬取）: {url}")
            return False
        
        # 检查robots.txt
        if not self.can_fetch(url):
            logger.debug(f"跳过URL（robots.txt禁止）: {url}")
            return False
        
        # 检查外部链接
        if not self.config.follow_external_links:
            base_domain = self.get_domain(list(self.crawled_urls.keys())[0]) if self.crawled_urls else ""
            if base_domain and self.get_domain(url) != base_domain:
                logger.debug(f"跳过URL（外部链接）: {url}")
                return False
        
        # 检查文件类型（跳过图片、PDF、字体、代码等静态资源）
        url_lower = url.lower()
        ignored_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.webp', '.bmp',
            '.pdf', '.zip', '.rar', '.exe', '.mp4', '.mp3', '.avi', '.mov',
            '.woff', '.woff2', '.ttf', '.eot', '.otf',  # 字体文件
            '.css', '.js', '.map',  # 代码文件
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        ]
        if any(url_lower.endswith(ext) for ext in ignored_extensions):
            logger.debug(f"跳过URL（文件类型）: {url}")
            return False
        
        # 检查静态资源路径模式
        static_patterns = [
            '/googlefonts/', '/google-fonts/', '/_hcms/', 
            '/wp-content/themes/', '/wp-includes/',
            '/assets/fonts/', '/static/fonts/',
        ]
        if any(pattern in url_lower for pattern in static_patterns):
            logger.debug(f"跳过URL（静态资源路径）: {url}")
            return False
        
        return True
    
    async def crawl_page(self, url: str, depth: int = 0) -> Optional[CrawledPage]:
        """爬取单个页面"""
        if not self.should_crawl_url(url, depth):
            return None
        
        # 随机延迟（避免请求过快）
        if self.config.random_delay and depth > 0:
            delay = random.uniform(self.config.request_delay_min, self.config.request_delay_max)
            await asyncio.sleep(delay)
        
        logger.info(f"爬取 [{depth}] {url}")
        
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        page = CrawledPage(url=url, depth=depth, status_code=0)
        
        try:
            async with self.session.get(url, headers=headers) as response:
                page.status_code = response.status
                page.content_type = response.headers.get('Content-Type', '')
                
                if response.status == 200:
                    html = await response.text()
                    page.html = html
                    
                    # 提取标题
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
                    if title_match:
                        page.title = title_match.group(1).strip()
                    
                    # 提取正文文本（简单版本）
                    text = self.extract_text_from_html(html)
                    page.content_text = text
                    
                    # 提取链接
                    links = self.extract_links_from_html(html, url)
                    page.links_found = links
                    
                    # 判断页面类型
                    page.page_type = self.classify_page_type(html, url, text)
                    
                    self.stats['successful'] += 1
                    
                else:
                    page.error = f"HTTP {response.status}"
                    self.stats['failed'] += 1
                
        except asyncio.TimeoutError:
            page.error = "请求超时"
            self.stats['failed'] += 1
        except aiohttp.ClientError as e:
            page.error = f"客户端错误: {e}"
            self.stats['failed'] += 1
        except Exception as e:
            page.error = f"未知错误: {e}"
            self.stats['failed'] += 1
        
        self.crawled_urls[url] = page
        self.stats['total_crawled'] += 1
        
        # 记录域名信息
        domain = self.get_domain(url)
        self.stats['unique_domains'].add(domain)
        
        return page
    
    def extract_text_from_html(self, html: str) -> str:
        """从HTML中提取文本内容"""
        # 移除脚本和样式
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # 替换多个空白字符为单个空格
        text = re.sub(r'\s+', ' ', text)
        
        # 解码HTML实体
        import html as html_module
        text = html_module.unescape(text)
        
        return text.strip()
    
    def extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """从HTML中提取链接 - 增强版，支持现代网站"""
        links = []
        
        # 模式1: href属性 (基础)
        href_patterns = [
            r'href=[\"\']([^\"\']+)[\"\']',  # 标准href
            r'data-href=[\"\']([^\"\']+)[\"\']',  # data-href属性
            r'data-url=[\"\']([^\"\']+)[\"\']',   # data-url属性
            r'url\([\"\']?([^\"\']+)[\"\']?\)',    # CSS url()
        ]
        
        # 模式2: JavaScript相关 (单引号或双引号)
        js_patterns = [
            r'load\([\"\']([^\"\']+)[\"\']\)',     # load('url')
            r'fetch\([\"\']([^\"\']+)[\"\']\)',    # fetch('url')
            r'ajax\([\"\']([^\"\']+)[\"\']\)',     # ajax('url')
            r'window\.location=[\"\']([^\"\']+)[\"\']',  # window.location='url'
            r'location\.href=[\"\']([^\"\']+)[\"\']',    # location.href='url'
        ]
        
        # 模式3: 常见API端点
        api_patterns = [
            r'/api/[^\"\']+',  # API端点
            r'/jobs/\d+',      # 职位详情页 (如/jobs/123)
            r'/job/\d+',       # 职位详情页 (如/job/123)
            r'/viewjob\?[^\"\']+',  # Indeed的viewjob
            r'/rc/[^\"\']+',   # Indeed的rc/clk链接
        ]
        
        all_patterns = href_patterns + js_patterns
        
        for pattern in all_patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                href = match.group(1) if pattern != r'/api/[^\"\']+' else match.group(0)
                
                # 跳过javascript和mailto等
                if href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:', 'blob:')):
                    continue
                
                # 对于相对路径，确保以斜杠开头
                if not re.match(r'^https?://', href) and not href.startswith('/'):
                    # 可能是相对路径但没有斜杠，尝试修复
                    if '?' in href or '=' in href:  # 看起来像查询参数
                        # 对于Indeed的start参数等
                        if 'start=' in href or 'page=' in href or 'p=' in href:
                            # 合并到base_url
                            import urllib.parse
                            base_parsed = urllib.parse.urlparse(base_url)
                            if '?' in base_url:
                                href = f"{base_url}&{href}" if '&' in base_url else f"{base_url}&{href}"
                            else:
                                href = f"{base_url}?{href}"
                        else:
                            href = f"/{href}"
                
                try:
                    normalized = self.normalize_url(href, base_url)
                    if normalized not in links:
                        links.append(normalized)
                except Exception as e:
                    logger.debug(f"链接规范化失败 {href}: {e}")
        
        # 特别处理：生成翻页链接（针对Indeed/Seek等网站）
        generated_links = self._generate_pagination_links(base_url)
        links.extend(generated_links)
        
        # 去重并过滤
        unique_links = []
        seen = set()
        for link in links:
            if link not in seen and link != base_url:
                # 额外过滤：移除跟踪参数等
                clean_link = self._clean_url(link)
                if clean_link and self._is_likely_job_related(clean_link, base_url):
                    seen.add(clean_link)
                    unique_links.append(clean_link)
        
        self.stats['total_links_found'] += len(unique_links)
        
        if unique_links:
            logger.debug(f"从页面提取到 {len(unique_links)} 个链接 (base: {base_url[:50]}...)")
            if len(unique_links) <= 10:
                for link in unique_links[:5]:
                    logger.debug(f"  → {link[:80]}...")
        
        return unique_links
    
    def _generate_pagination_links(self, base_url: str) -> List[str]:
        """生成翻页链接（针对Indeed/Seek等网站）"""
        generated = []
        
        # 分析URL类型
        url_lower = base_url.lower()
        
        # Indeed模式: &start=参数
        if 'indeed.com' in url_lower and 'start=' not in url_lower:
            # 生成前5页
            for start in [10, 20, 30, 40, 50]:
                if '?' in base_url:
                    paginated = f"{base_url}&start={start}"
                else:
                    paginated = f"{base_url}?start={start}"
                generated.append(paginated)
        
        # Seek模式: page参数
        elif 'seek.com.au' in url_lower and 'page=' not in url_lower:
            for page in [2, 3, 4, 5]:
                if '?' in base_url:
                    paginated = f"{base_url}&page={page}"
                else:
                    paginated = f"{base_url}?page={page}"
                generated.append(paginated)
        
        # 通用模式: page参数
        elif any(domain in url_lower for domain in ['jobs', 'careers', 'vacancies']):
            for page in [2, 3]:
                if '?' in base_url:
                    paginated = f"{base_url}&page={page}"
                else:
                    paginated = f"{base_url}?page={page}"
                generated.append(paginated)
        
        return generated
    
    def _clean_url(self, url: str) -> str:
        """清理URL，移除跟踪参数等"""
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            
            # 移除常见跟踪参数
            tracking_params = [
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'msclkid', 'ref', 'source', 'cid', 'ncid',
                'trk', 'trkInfo', 'trackingId'
            ]
            
            if parsed.query:
                query_params = urllib.parse.parse_qs(parsed.query)
                # 移除跟踪参数
                for param in tracking_params:
                    query_params.pop(param, None)
                
                # 重建查询字符串
                if query_params:
                    new_query = urllib.parse.urlencode(query_params, doseq=True)
                else:
                    new_query = ''
                
                # 重建URL
                cleaned = urllib.parse.urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                return cleaned
            else:
                return url
        except Exception:
            return url
    
    def _is_likely_job_related(self, url: str, base_url: str) -> bool:
        """判断URL是否可能与职位相关"""
        url_lower = url.lower()
        base_lower = base_url.lower()
        
        # 跳过明显无关的
        skip_patterns = [
            '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.css', '.js', '.svg',
            '/cdn-cgi/', '/assets/', '/static/', '/uploads/', '/images/',
            'login', 'signup', 'register', 'logout', 'account', 'profile',
            'privacy', 'terms', 'policy', 'contact', 'about', 'help'
        ]
        
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # 检查是否与职位相关
        job_patterns = [
            'job', 'jobs', 'career', 'careers', 'position', 'positions',
            'vacancy', 'vacancies', 'opportunity', 'opportunities',
            'role', 'roles', 'employment', 'recruitment',
            'viewjob', 'apply', 'application', 'hire', 'hiring'
        ]
        
        for pattern in job_patterns:
            if pattern in url_lower:
                return True
        
        # 检查URL结构
        if re.search(r'/jobs?/\d+', url_lower):  # /jobs/123 或 /job/123
            return True
        
        if re.search(r'/careers?/\d+', url_lower):  # /careers/123
            return True
        
        # 检查是否在同一域名下
        try:
            import urllib.parse
            url_domain = urllib.parse.urlparse(url_lower).netloc
            base_domain = urllib.parse.urlparse(base_lower).netloc
            
            if url_domain == base_domain:
                # 同域名下的其他页面可能相关
                return True
        except:
            pass
        
        return False
    
    def classify_page_type(self, html: str, url: str, text: str) -> str:
        """判断页面类型"""
        url_lower = url.lower()
        
        # 检查常见页面类型模式
        if re.search(r'job|career|position|vacancy', text, re.IGNORECASE) and len(text) > 500:
            return "detail"  # 职位详情页
        
        if re.search(r'jobs?.*search|search.*jobs?', text, re.IGNORECASE):
            return "list"  # 职位列表页
        
        if re.search(r'apply|application|submit|cv|resume', text, re.IGNORECASE):
            return "form"  # 申请表页
        
        # 根据URL路径判断
        if any(pattern in url_lower for pattern in ['/jobs/', '/careers/', '/vacancies/']):
            if '/apply' in url_lower or '/application' in url_lower:
                return "form"
            elif re.search(r'/jobs?/\d+|/careers?/\d+', url_lower):
                return "detail"
            else:
                return "list"
        
        # 根据内容长度判断
        word_count = len(text.split())
        if word_count > 1000:
            return "detail"
        elif word_count > 100:
            return "list"
        
        return "other"
    
    async def deep_crawl(self, start_url: str) -> Dict[str, Any]:
        """
        深度爬取网站
        
        Args:
            start_url: 起始URL
            
        Returns:
            爬取结果字典
        """
        logger.info(f"开始深度爬取: {start_url}")
        
        # 启动会话
        await self.start()
        
        # 初始化URL队列
        url_queue = asyncio.Queue()
        await url_queue.put((start_url, 0))  # (url, depth)
        
        # 发现URL集合（避免重复加入队列）
        discovered_set = set([start_url])
        
        # 创建工作者任务
        workers = [self._crawl_worker(url_queue, discovered_set) 
                  for _ in range(self.config.max_concurrent)]
        
        # 等待所有工作者完成
        await asyncio.gather(*workers)
        
        # 收集结果
        results = self._collect_results()
        
        logger.info(f"深度爬取完成: {self.stats['total_crawled']} 个页面")
        
        # 保存结果
        await self.save_results(results)
        
        return results
    
    async def _crawl_worker(self, url_queue: asyncio.Queue, discovered_set: Set[str]):
        """爬取工作者"""
        try:
            while not url_queue.empty() and self.stats['total_crawled'] < self.config.max_pages:
                try:
                    url, depth = await asyncio.wait_for(url_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # 爬取页面
                page = await self.crawl_page(url, depth)
                
                if page and page.is_successful:
                    # 发现新链接
                    new_depth = depth + 1
                    if new_depth < self.config.max_depth:
                        for link in page.links_found:
                            if (link not in discovered_set and 
                                self.should_crawl_url(link, new_depth)):
                                discovered_set.add(link)
                                await url_queue.put((link, new_depth))
                
                url_queue.task_done()
                
        except Exception as e:
            logger.error(f"爬取工作者异常: {e}")
    
    def _collect_results(self) -> Dict[str, Any]:
        """收集爬取结果"""
        elapsed = time.time() - self.stats['start_time']
        
        # 按类型分类页面
        pages_by_type = defaultdict(list)
        for page in self.crawled_urls.values():
            if page.is_successful:
                pages_by_type[page.page_type].append({
                    'url': page.url,
                    'title': page.title,
                    'depth': page.depth,
                    'content_preview': page.content_text[:200] + '...' if page.content_text else ''
                })
        
        # 提取可能的职位信息
        potential_jobs = []
        for page in self.crawled_urls.values():
            if page.page_type in ['detail', 'form'] and page.is_successful:
                potential_jobs.append({
                    'url': page.url,
                    'title': page.title,
                    'content': page.content_text,
                    'depth': page.depth
                })
        
        results = {
            'stats': {
                'total_crawled': self.stats['total_crawled'],
                'successful': self.stats['successful'],
                'failed': self.stats['failed'],
                'success_rate': self.stats['successful'] / self.stats['total_crawled'] if self.stats['total_crawled'] > 0 else 0,
                'total_links_found': self.stats['total_links_found'],
                'unique_domains': len(self.stats['unique_domains']),
                'elapsed_seconds': elapsed,
                'pages_per_second': self.stats['total_crawled'] / elapsed if elapsed > 0 else 0
            },
            'pages_by_type': dict(pages_by_type),
            'potential_jobs': potential_jobs,
            'crawled_urls': list(self.crawled_urls.keys()),
            'config': {
                'max_depth': self.config.max_depth,
                'max_pages': self.config.max_pages,
                'max_concurrent': self.config.max_concurrent
            }
        }
        
        return results
    
    async def save_results(self, results: Dict[str, Any]):
        """保存爬取结果"""
        output_dir = self.output_dir
        
        # 保存主结果
        results_file = output_dir / f"deep_crawl_results_{int(time.time())}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # 保存详细的页面信息
        pages_file = output_dir / f"crawled_pages_{int(time.time())}.json"
        pages_data = []
        for url, page in self.crawled_urls.items():
            pages_data.append({
                'url': page.url,
                'depth': page.depth,
                'status_code': page.status_code,
                'page_type': page.page_type,
                'title': page.title,
                'content_length': len(page.content_text),
                'links_found': len(page.links_found),
                'error': page.error
            })
        
        with open(pages_file, 'w', encoding='utf-8') as f:
            json.dump(pages_data, f, indent=2, ensure_ascii=False)
        
        # 保存文本内容
        if self.config.save_text:
            text_dir = output_dir / "text_content"
            text_dir.mkdir(exist_ok=True)
            
            for url, page in self.crawled_urls.items():
                if page.content_text:
                    # 创建安全的文件名
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    filename = f"{page.page_type}_{url_hash}.txt"
                    filepath = text_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"URL: {url}\n")
                        f.write(f"Title: {page.title}\n")
                        f.write(f"Depth: {page.depth}\n")
                        f.write(f"Type: {page.page_type}\n")
                        f.write("=" * 80 + "\n")
                        f.write(page.content_text)
        
        logger.info(f"结果已保存到: {output_dir}")

    def get_stats(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        elapsed = time.time() - self.stats['start_time'] if not self.stats['end_time'] else self.stats['end_time'] - self.stats['start_time']
        
        return {
            'total_crawled': self.stats['total_crawled'],
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'success_rate': self.stats['successful'] / self.stats['total_crawled'] if self.stats['total_crawled'] > 0 else 0,
            'total_links_found': self.stats['total_links_found'],
            'unique_domains': len(self.stats['unique_domains']),
            'elapsed_seconds': elapsed,
            'pages_per_second': self.stats['total_crawled'] / elapsed if elapsed > 0 else 0,
            'crawled_urls': list(self.crawled_urls.keys())[:10]  # 前10个URL
        }