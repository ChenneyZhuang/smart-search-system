#!/usr/bin/env python3
"""
链接发现引擎 - 智能链接提取和分类
专门为岗位网站优化，识别分页、职位详情和相关链接
"""

import re
import urllib.parse
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class LinkInfo:
    """链接信息"""
    url: str
    text: str = ""  # 链接文本
    parent_url: str = ""
    anchor_text: str = ""
    depth: int = 0
    link_type: str = "unknown"  # pagination, job_detail, job_list, navigation, external, other
    priority: int = 50  # 优先级 (1-100, 越高越优先)
    confidence: float = 0.5  # 置信度 (0-1)
    
    # 来源信息
    found_in: str = "html"  # html, sitemap, robots
    selector: str = ""
    position: Tuple[int, int] = (0, 0)  # 在页面中的位置
    
    def __post_init__(self):
        # 确保URL规范
        if self.url:
            self.url = self.url.strip()

@dataclass
class WebsiteLinkStrategy:
    """网站链接策略"""
    name: str  # indeed, seek, aps等
    domain_patterns: List[str]  # 匹配的域名模式
    pagination_patterns: List[str] = field(default_factory=list)  # 分页模式
    job_detail_patterns: List[str] = field(default_factory=list)  # 职位详情页模式
    job_list_patterns: List[str] = field(default_factory=list)    # 职位列表页模式
    ignore_patterns: List[str] = field(default_factory=list)      # 忽略的模式
    link_selectors: Dict[str, str] = field(default_factory=dict)  # CSS选择器映射
    priority_rules: Dict[str, int] = field(default_factory=dict)  # 优先级规则
    
    def __post_init__(self):
        # 确保模式列表不为None
        if self.pagination_patterns is None:
            self.pagination_patterns = []
        if self.job_detail_patterns is None:
            self.job_detail_patterns = []
        if self.job_list_patterns is None:
            self.job_list_patterns = []
        if self.ignore_patterns is None:
            self.ignore_patterns = []
        if self.link_selectors is None:
            self.link_selectors = {}
        if self.priority_rules is None:
            self.priority_rules = {}

class LinkExtractor:
    """链接提取器 - 从HTML中提取和分类链接"""
    
    # 预定义的网站策略
    PREDEFINED_STRATEGIES = {
        "indeed": WebsiteLinkStrategy(
            name="indeed",
            domain_patterns=["indeed.com", "indeed.co", "indeed.au"],
            pagination_patterns=[
                r"start=\d+",
                r"page=\d+", 
                r"&p=\d+",
                r"start=(\d+)",
                r"下一页|next|>|›",
                r"page-\d+",
                r"pg-\d+"
            ],
            job_detail_patterns=[
                r"/jobs?/view",
                r"/rc/",
                r"/clk\?",
                r"jk=",
                r"/job/",
                r"viewjob\?",
                r"jobad/"
            ],
            job_list_patterns=[
                r"/jobs\?",
                r"/search\?",
                r"/jobs/search",
                r"/jobs/"
            ],
            ignore_patterns=[
                "login",
                "signup", 
                "employer",
                "account",
                "profile",
                "resume",
                "myjobs",
                "/recommendations",
                "/salaries",
                "/companies"
            ],
            link_selectors={
                "job_container": ".job_seen_beacon",
                "job_title": ".jcs-JobTitle",
                "job_link": "a[data-jk]",
                "pagination": ".pagination-list a",
                "next_page": "a[aria-label='Next']"
            },
            priority_rules={
                "job_detail": 90,
                "job_list": 80,
                "pagination": 70,
                "navigation": 60,
                "other": 30
            }
        ),
        
        "seek": WebsiteLinkStrategy(
            name="seek",
            domain_patterns=["seek.com.au", "seek.co.nz"],
            pagination_patterns=[
                r"page=\d+",
                r"offset=\d+",
                r"下一页|next|>|›",
                r"page-\d+",
                r"pg-\d+"
            ],
            job_detail_patterns=[
                r"/job/\d+",
                r"jobid=",
                r"/jobad/",
                r"viewjob\?",
                r"/jobs/"
            ],
            job_list_patterns=[
                r"/jobs/",
                r"/job-search/",
                r"/jobs-in-",
                r"/jobs\?"
            ],
            ignore_patterns=[
                "account",
                "profile",
                "login",
                "signup",
                "employer",
                "dashboard",
                "saved-jobs",
                "applications",
                "alerts"
            ],
            link_selectors={
                "job_container": "[data-automation='normalJob']",
                "job_title": "[data-automation='jobTitle']",
                "job_link": "a[data-automation='jobTitle']",
                "pagination": "[data-automation='pagination'] a",
                "next_page": "a[aria-label='Next']"
            },
            priority_rules={
                "job_detail": 90,
                "job_list": 85,
                "pagination": 75,
                "navigation": 65,
                "other": 35
            }
        ),
        
        "aps": WebsiteLinkStrategy(
            name="aps",
            domain_patterns=["apsjobs.gov.au"],
            pagination_patterns=[
                r"pageNumber=\d+",
                r"页码=\d+",
                r"next|下一页",
                r"page-\d+"
            ],
            job_detail_patterns=[
                r"/job/\d+",
                r"jobId=",
                r"/jobs/",
                r"/position/"
            ],
            job_list_patterns=[
                r"/jobs/search",
                r"/jobs\?",
                r"/job-list",
                r"/vacancies"
            ],
            ignore_patterns=[
                "login",
                "register",
                "account",
                "profile",
                "admin",
                "dashboard",
                "secure"
            ],
            link_selectors={
                "job_container": ".job-listing-item",
                "job_title": ".job-title a",
                "job_link": ".job-link",
                "pagination": ".pagination a",
                "next_page": "a.next"
            },
            priority_rules={
                "job_detail": 95,
                "job_list": 85,
                "pagination": 70,
                "navigation": 60,
                "other": 40
            }
        ),
        
        "linkedin": WebsiteLinkStrategy(
            name="linkedin",
            domain_patterns=["linkedin.com", "linked.in"],
            pagination_patterns=[
                r"start=\d+",
                r"page=\d+",
                r"下一页|next|>|›"
            ],
            job_detail_patterns=[
                r"/jobs/view/",
                r"/jobs/collections/",
                r"currentJobId=",
                r"/job-posting/"
            ],
            job_list_patterns=[
                r"/jobs/search/",
                r"/jobs/",
                r"/job/"
            ],
            ignore_patterns=[
                "login",
                "signup",
                "profile",
                "connections",
                "messaging",
                "notifications",
                "premium",
                "learning"
            ],
            link_selectors={
                "job_container": ".jobs-search-results-list__item",
                "job_title": ".job-card-list__title",
                "job_link": ".job-card-container__link",
                "pagination": ".artdeco-pagination__pages a",
                "next_page": "button[aria-label='Next']"
            },
            priority_rules={
                "job_detail": 85,
                "job_list": 80,
                "pagination": 65,
                "navigation": 55,
                "other": 30
            }
        ),
        
        "glassdoor": WebsiteLinkStrategy(
            name="glassdoor",
            domain_patterns=["glassdoor.com", "glassdoor.ca"],
            pagination_patterns=[
                r"p=\d+",
                r"page=\d+",
                r"下一页|next|>|›",
                r"IP\d+"  # 如 IP2, IP3
            ],
            job_detail_patterns=[
                r"/Job/",
                r"jobListingId=",
                r"/job-listing/",
                r"/GD/JobListing/"
            ],
            job_list_patterns=[
                "/jobs/",
                "/Find/",
                "/Job/"
            ],
            ignore_patterns=[
                "login",
                "signup",
                "account",
                "profile",
                "reviews",
                "salaries",
                "interviews",
                "companies"
            ],
            link_selectors={
                "job_container": ".react-job-listing",
                "job_title": ".jobLink",
                "job_link": "a[data-test='job-link']",
                "pagination": ".pagination__PaginationStyle__page a",
                "next_page": "a[data-test='pagination-next']"
            },
            priority_rules={
                "job_detail": 88,
                "job_list": 82,
                "pagination": 72,
                "navigation": 62,
                "other": 32
            }
        )
    }
    
    def __init__(self, custom_strategies: Optional[Dict[str, WebsiteLinkStrategy]] = None):
        """初始化链接提取器"""
        self.strategies = self.PREDEFINED_STRATEGIES.copy()
        if custom_strategies:
            self.strategies.update(custom_strategies)
        
        # 编译正则表达式缓存
        self._regex_cache = {}
        
        logger.info(f"链接提取器初始化完成，支持 {len(self.strategies)} 种网站策略")
    
    def detect_website_type(self, url: str) -> Optional[str]:
        """根据URL检测网站类型"""
        for strategy_name, strategy in self.strategies.items():
            for domain_pattern in strategy.domain_patterns:
                if domain_pattern in url:
                    return strategy_name
        
        # 尝试根据常见模式推断
        url_lower = url.lower()
        if "indeed" in url_lower:
            return "indeed"
        elif "seek" in url_lower:
            return "seek"
        elif "apsjobs" in url_lower:
            return "aps"
        elif "linkedin" in url_lower:
            return "linkedin"
        elif "glassdoor" in url_lower:
            return "glassdoor"
        
        return None
    
    def get_strategy_for_url(self, url: str) -> Optional[WebsiteLinkStrategy]:
        """获取URL对应的策略"""
        website_type = self.detect_website_type(url)
        if website_type:
            return self.strategies.get(website_type)
        return None
    
    def extract_links_from_html(self, html: str, base_url: str, 
                               strategy: Optional[WebsiteLinkStrategy] = None) -> List[LinkInfo]:
        """
        从HTML中提取链接
        
        Args:
            html: HTML内容
            base_url: 基础URL（用于相对链接转换）
            strategy: 链接策略，如果为None则自动检测
            
        Returns:
            链接信息列表
        """
        if not strategy:
            strategy = self.get_strategy_for_url(base_url)
        
        links = []
        
        # 方法1: 正则表达式提取（快速但可能不完整）
        links.extend(self._extract_links_by_regex(html, base_url, strategy))
        
        # 方法2: 简单HTML解析（更准确）
        links.extend(self._extract_links_by_simple_parse(html, base_url, strategy))
        
        # 分类和过滤链接
        classified_links = self.classify_links(links, strategy)
        
        # 去重（基于URL）
        unique_links = self._deduplicate_links(classified_links)
        
        return unique_links
    
    def _extract_links_by_regex(self, html: str, base_url: str, 
                               strategy: Optional[WebsiteLinkStrategy]) -> List[LinkInfo]:
        """使用正则表达式提取链接（快速方法）"""
        links = []
        
        # 匹配href属性
        href_pattern = r'href=["\']([^"\']+)["\']'
        for match in re.finditer(href_pattern, html, re.IGNORECASE):
            href = match.group(1)
            link_info = self._create_link_info(href, base_url, strategy, "href")
            if link_info:
                links.append(link_info)
        
        # 匹配a标签（提取链接文本）
        a_tag_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        for match in re.finditer(a_tag_pattern, html, re.DOTALL | re.IGNORECASE):
            href = match.group(1)
            text = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # 移除内部标签
            
            link_info = self._create_link_info(href, base_url, strategy, "a_tag")
            if link_info:
                link_info.text = text
                link_info.anchor_text = text
                links.append(link_info)
        
        return links
    
    def _extract_links_by_simple_parse(self, html: str, base_url: str,
                                      strategy: Optional[WebsiteLinkStrategy]) -> List[LinkInfo]:
        """使用简单HTML解析提取链接（更准确）"""
        links = []
        
        # 这里可以集成更复杂的HTML解析器，如BeautifulSoup
        # 目前使用正则表达式增强版本
        
        # 提取所有可能的链接标签
        link_tags = [
            ('a', 'href'),
            ('link', 'href'),
            ('area', 'href'),
            ('iframe', 'src'),
            ('img', 'src'),
            ('script', 'src'),
            ('form', 'action')
        ]
        
        for tag, attr in link_tags:
            pattern = fr'<{tag}[^>]*{attr}=["\']([^"\']+)["\'][^>]*>'
            for match in re.finditer(pattern, html, re.IGNORECASE):
                url = match.group(1)
                link_info = self._create_link_info(url, base_url, strategy, f"{tag}_{attr}")
                if link_info:
                    links.append(link_info)
        
        return links
    
    def _create_link_info(self, url: str, base_url: str, 
                         strategy: Optional[WebsiteLinkStrategy],
                         source: str) -> Optional[LinkInfo]:
        """创建链接信息对象"""
        if not url or url.strip() == "":
            return None
        
        # 跳过常见的不需要处理的URL
        url_lower = url.lower()
        if url_lower.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:', 'file:')):
            return None
        
        # 规范化URL
        try:
            normalized = self._normalize_url(url, base_url)
        except Exception as e:
            logger.debug(f"URL规范化失败 {url}: {e}")
            return None
        
        # 创建链接信息
        link_info = LinkInfo(
            url=normalized,
            parent_url=base_url,
            found_in=source
        )
        
        return link_info
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """规范化URL"""
        # 如果是相对URL，转换为绝对URL
        if not re.match(r'^https?://', url, re.IGNORECASE):
            url = urllib.parse.urljoin(base_url, url)
        
        # 解析URL
        parsed = urllib.parse.urlparse(url)
        
        # 标准化
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower() if parsed.scheme else 'http',
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
    
    def classify_links(self, links: List[LinkInfo], 
                      strategy: Optional[WebsiteLinkStrategy]) -> List[LinkInfo]:
        """分类链接（分页、职位详情等）"""
        if not strategy:
            # 使用通用策略
            strategy = WebsiteLinkStrategy(
                name="generic",
                domain_patterns=[],
                pagination_patterns=[r"page=\d+", r"start=\d+", r"下一页|next|>|›"],
                job_detail_patterns=[r"/job/", r"jobid=", r"viewjob"],
                job_list_patterns=[r"/jobs", r"/careers", r"/vacancies"],
                ignore_patterns=["login", "signup", "account", "profile"]
            )
        
        for link in links:
            link.link_type = self._classify_single_link(link, strategy)
            link.priority = self._calculate_priority(link, strategy)
            link.confidence = self._calculate_confidence(link, strategy)
        
        return links
    
    def _classify_single_link(self, link: LinkInfo, strategy: WebsiteLinkStrategy) -> str:
        """分类单个链接"""
        url_lower = link.url.lower()
        text_lower = link.text.lower() if link.text else ""
        
        # 检查忽略模式
        for pattern in strategy.ignore_patterns:
            if pattern and (pattern in url_lower or pattern in text_lower):
                return "ignored"
        
        # 检查分页模式
        for pattern in strategy.pagination_patterns:
            if pattern and self._matches_pattern(url_lower, pattern):
                return "pagination"
        
        # 检查职位详情模式
        for pattern in strategy.job_detail_patterns:
            if pattern and self._matches_pattern(url_lower, pattern):
                return "job_detail"
        
        # 检查职位列表模式
        for pattern in strategy.job_list_patterns:
            if pattern and self._matches_pattern(url_lower, pattern):
                return "job_list"
        
        # 根据链接文本判断
        if any(word in text_lower for word in ["job", "career", "position", "vacancy", "apply"]):
            return "job_related"
        
        # 检查是否外部链接
        parent_domain = self._get_domain(link.parent_url)
        current_domain = self._get_domain(link.url)
        if parent_domain and current_domain and parent_domain != current_domain:
            return "external"
        
        return "other"
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """检查文本是否匹配模式"""
        # 检查缓存
        cache_key = pattern
        if cache_key not in self._regex_cache:
            try:
                # 如果是正则表达式模式
                if pattern.startswith('^') or pattern.endswith('$') or '.*' in pattern:
                    self._regex_cache[cache_key] = re.compile(pattern, re.IGNORECASE)
                else:
                    # 普通字符串匹配
                    self._regex_cache[cache_key] = re.compile(re.escape(pattern), re.IGNORECASE)
            except re.error:
                # 如果正则表达式编译失败，使用普通字符串匹配
                self._regex_cache[cache_key] = None
        
        regex = self._regex_cache[cache_key]
        if regex:
            return bool(regex.search(text))
        else:
            return pattern in text
    
    def _calculate_priority(self, link: LinkInfo, strategy: WebsiteLinkStrategy) -> int:
        """计算链接优先级"""
        base_priority = strategy.priority_rules.get(link.link_type, 50)
        
        # 根据其他因素调整优先级
        adjustments = 0
        
        # 链接深度较浅的优先级更高
        if link.depth == 0:
            adjustments += 10
        elif link.depth <= 2:
            adjustments += 5
        
        # 链接文本包含关键词的优先级更高
        if link.text:
            text_lower = link.text.lower()
            if any(word in text_lower for word in ["apply", "urgent", "immediate", "new"]):
                adjustments += 15
            elif any(word in text_lower for word in ["job", "career", "position"]):
                adjustments += 10
        
        # URL路径短的优先级更高（通常更重要）
        path_len = len(urllib.parse.urlparse(link.url).path)
        if path_len < 20:
            adjustments += 5
        elif path_len > 100:
            adjustments -= 5
        
        # 确保优先级在1-100范围内
        priority = base_priority + adjustments
        return max(1, min(100, priority))
    
    def _calculate_confidence(self, link: LinkInfo, strategy: WebsiteLinkStrategy) -> float:
        """计算链接分类置信度"""
        confidence = 0.5  # 基础置信度
        
        # 根据分类类型调整置信度
        if link.link_type == "pagination":
            # 分页链接通常容易识别
            confidence = 0.8
        elif link.link_type == "job_detail":
            confidence = 0.7
        elif link.link_type == "job_list":
            confidence = 0.6
        elif link.link_type == "ignored":
            confidence = 0.9  # 忽略的链接置信度高
        
        # 根据匹配模式数量调整
        url_lower = link.url.lower()
        
        # 检查是否匹配多个特征
        feature_count = 0
        if any(pattern in url_lower for pattern in ["/job/", "jobid=", "viewjob"]):
            feature_count += 1
        if any(pattern in url_lower for pattern in ["page=", "start=", "p="]):
            feature_count += 1
        if link.text and any(word in link.text.lower() for word in ["job", "career"]):
            feature_count += 1
        
        if feature_count >= 2:
            confidence = min(1.0, confidence + 0.2)
        
        return confidence
    
    def _get_domain(self, url: str) -> str:
        """获取URL的域名"""
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc.lower()
        except:
            return ""
    
    def _deduplicate_links(self, links: List[LinkInfo]) -> List[LinkInfo]:
        """去重链接（基于URL）"""
        unique_links = []
        seen_urls = set()
        
        for link in links:
            if link.url not in seen_urls:
                seen_urls.add(link.url)
                unique_links.append(link)
        
        return unique_links
    
    def prioritize_links(self, links: List[LinkInfo], 
                        max_links: int = 100) -> List[LinkInfo]:
        """按优先级排序链接"""
        # 过滤掉忽略的链接
        filtered = [link for link in links if link.link_type != "ignored"]
        
        # 按优先级排序（降序）
        sorted_links = sorted(filtered, key=lambda x: (-x.priority, -x.confidence))
        
        # 限制数量
        return sorted_links[:max_links]
    
    def analyze_link_patterns(self, links: List[LinkInfo]) -> Dict[str, Any]:
        """分析链接模式"""
        analysis = {
            "total_links": len(links),
            "by_type": defaultdict(int),
            "by_priority": defaultdict(int),
            "domains": set(),
            "url_patterns": defaultdict(int)
        }
        
        for link in links:
            analysis["by_type"][link.link_type] += 1
            
            priority_group = (link.priority // 10) * 10  # 10, 20, 30, ...
            analysis["by_priority"][priority_group] += 1
            
            domain = self._get_domain(link.url)
            if domain:
                analysis["domains"].add(domain)
            
            # 分析URL路径模式
            try:
                parsed = urllib.parse.urlparse(link.url)
                path = parsed.path
                if path:
                    # 提取路径中的数字（如/job/12345中的12345）
                    numbers = re.findall(r'\d+', path)
                    if numbers:
                        pattern = re.sub(r'\d+', '{id}', path)
                        analysis["url_patterns"][pattern] += 1
            except:
                pass
        
        return analysis


class LinkDiscoveryEngine:
    """链接发现引擎 - 整合多种发现方法"""
    
    def __init__(self, extractor: Optional[LinkExtractor] = None):
        self.extractor = extractor or LinkExtractor()
        
        # 发现方法
        self.discovery_methods = [
            self.discover_from_html,
            self.discover_from_sitemap,
            self.discover_from_robots,
            self.discover_from_pagination_patterns
        ]
        
        logger.info("链接发现引擎初始化完成")
    
    async def discover_links(self, base_url: str, 
                           html_content: Optional[str] = None,
                           max_links: int = 200) -> List[LinkInfo]:
        """
        发现所有相关链接
        
        Args:
            base_url: 基础URL
            html_content: HTML内容（如果已有）
            max_links: 最大链接数
            
        Returns:
            链接信息列表
        """
        all_links = []
        
        # 1. 从HTML中发现链接
        if html_content:
            html_links = self.discover_from_html(html_content, base_url)
            all_links.extend(html_links)
            logger.info(f"从HTML中发现 {len(html_links)} 个链接")
        
        # 2. 从网站地图中发现链接
        sitemap_links = await self.discover_from_sitemap(base_url)
        all_links.extend(sitemap_links)
        logger.info(f"从网站地图中发现 {len(sitemap_links)} 个链接")
        
        # 3. 从robots.txt中发现链接
        robots_links = await self.discover_from_robots(base_url)
        all_links.extend(robots_links)
        logger.info(f"从robots.txt中发现 {len(robots_links)} 个链接")
        
        # 去重和分类
        unique_links = self.extractor._deduplicate_links(all_links)
        classified_links = self.extractor.classify_links(unique_links, 
                                                       self.extractor.get_strategy_for_url(base_url))
        
        # 按优先级排序
        prioritized = self.extractor.prioritize_links(classified_links, max_links)
        
        return prioritized
    
    def discover_from_html(self, html: str, base_url: str) -> List[LinkInfo]:
        """从HTML中发现链接"""
        strategy = self.extractor.get_strategy_for_url(base_url)
        return self.extractor.extract_links_from_html(html, base_url, strategy)
    
    async def discover_from_sitemap(self, base_url: str) -> List[LinkInfo]:
        """从网站地图中发现链接"""
        import aiohttp
        import xml.etree.ElementTree as ET
        
        links = []
        
        # 常见的网站地图位置
        sitemap_locations = [
            "/sitemap.xml",
            "/sitemap_index.xml", 
            "/sitemap/sitemap.xml",
            "/sitemap.php",
            "/robots.txt"  # robots.txt中可能包含sitemap位置
        ]
        
        try:
            # 首先检查robots.txt中的sitemap
            robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=10) as response:
                    if response.status == 200:
                        robots_content = await response.text()
                        for line in robots_content.split('\n'):
                            if line.lower().startswith('sitemap:'):
                                sitemap_url = line.split(':', 1)[1].strip()
                                sitemap_locations.insert(0, sitemap_url)
            
            # 尝试每个网站地图位置
            for location in sitemap_locations:
                sitemap_url = urllib.parse.urljoin(base_url, location)
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(sitemap_url, timeout=15) as response:
                            if response.status == 200:
                                content = await response.text()
                                
                                # 解析XML
                                try:
                                    root = ET.fromstring(content)
                                    
                                    # 检查是sitemap索引还是普通sitemap
                                    if root.tag.endswith('sitemapindex'):
                                        # sitemap索引，需要进一步获取子sitemap
                                        for sitemap in root.findall('.//{*}sitemap/{*}loc'):
                                            child_sitemap_url = sitemap.text
                                            if child_sitemap_url:
                                                # 递归获取子sitemap
                                                child_links = await self.discover_from_sitemap(child_sitemap_url)
                                                links.extend(child_links)
                                    else:
                                        # 普通sitemap
                                        for url in root.findall('.//{*}url/{*}loc'):
                                            if url.text:
                                                link = LinkInfo(
                                                    url=url.text,
                                                    parent_url=base_url,
                                                    found_in="sitemap",
                                                    link_type="sitemap"
                                                )
                                                links.append(link)
                                    
                                    logger.debug(f"从 {sitemap_url} 解析网站地图成功")
                                    break  # 成功找到并解析一个sitemap就停止
                                    
                                except ET.ParseError:
                                    # 可能不是XML格式，尝试文本格式
                                    for line in content.split('\n'):
                                        line = line.strip()
                                        if line and (line.startswith('http://') or line.startswith('https://')):
                                            link = LinkInfo(
                                                url=line,
                                                parent_url=base_url,
                                                found_in="sitemap",
                                                link_type="sitemap"
                                            )
                                            links.append(link)
                except Exception as e:
                    logger.debug(f"无法获取网站地图 {sitemap_url}: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"网站地图发现异常: {e}")
        
        return links
    
    async def discover_from_robots(self, base_url: str) -> List[LinkInfo]:
        """从robots.txt中发现链接"""
        import aiohttp
        
        links = []
        
        try:
            robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                if ':' in line:
                                    key, value = line.split(':', 1)
                                    key = key.strip().lower()
                                    value = value.strip()
                                    
                                    if key == 'allow' or key == 'disallow':
                                        # 这些是路径模式，不是完整URL
                                        if value and value != '/':
                                            full_url = urllib.parse.urljoin(base_url, value)
                                            link = LinkInfo(
                                                url=full_url,
                                                parent_url=base_url,
                                                found_in="robots",
                                                link_type="robots"
                                            )
                                            links.append(link)
        
        except Exception as e:
            logger.debug(f"robots.txt发现异常: {e}")
        
        return links
    
    def discover_from_pagination_patterns(self, base_url: str, 
                                        current_page: int = 1,
                                        max_pages: int = 10) -> List[LinkInfo]:
        """根据分页模式发现链接"""
        links = []
        
        strategy = self.extractor.get_strategy_for_url(base_url)
        if not strategy:
            return links
        
        # 生成分页URL
        for pattern in strategy.pagination_patterns:
            if '{' in pattern and '}' in pattern:
                # 这是模板模式，如 page={}, start={}
                for page_num in range(1, max_pages + 1):
                    page_url = base_url
                    if '?' in base_url:
                        page_url += f"&{pattern.format(page_num)}"
                    else:
                        page_url += f"?{pattern.format(page_num)}"
                    
                    link = LinkInfo(
                        url=page_url,
                        parent_url=base_url,
                        found_in="pagination_pattern",
                        link_type="pagination",
                        priority=70
                    )
                    links.append(link)
        
        return links