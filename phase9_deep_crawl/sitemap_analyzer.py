#!/usr/bin/env python3
"""
网站地图分析器 - 专门发现和解析网站地图
支持XML、TXT、HTML格式，递归获取子sitemap，智能URL过滤
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
import urllib.parse
import re
import json
from datetime import datetime
import hashlib
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class SitemapURL:
    """网站地图中的URL信息"""
    url: str
    lastmod: Optional[str] = None
    changefreq: Optional[str] = None  # always, hourly, daily, weekly, monthly, yearly, never
    priority: Optional[float] = None  # 0.0 - 1.0
    sitemap_source: str = ""  # 来源sitemap文件
    discovered_at: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def __post_init__(self):
        # 确保URL规范
        if self.url:
            self.url = self.url.strip()
        
        # 解析最后修改日期
        if self.lastmod:
            try:
                # 尝试解析ISO格式日期
                if 'T' in self.lastmod:
                    dt = datetime.fromisoformat(self.lastmod.replace('Z', '+00:00'))
                    self.lastmod = dt.isoformat()
            except:
                pass
    
    @property
    def domain(self) -> str:
        """获取URL的域名"""
        try:
            parsed = urllib.parse.urlparse(self.url)
            return parsed.netloc
        except:
            return ""
    
    @property
    def path(self) -> str:
        """获取URL的路径"""
        try:
            parsed = urllib.parse.urlparse(self.url)
            return parsed.path
        except:
            return ""

@dataclass
class SitemapInfo:
    """网站地图信息"""
    url: str
    content_type: str = ""  # xml, txt, html, unknown
    url_count: int = 0
    is_index: bool = False  # 是否是sitemap索引文件
    child_sitemaps: List[str] = field(default_factory=list)  # 子sitemap URL列表
    last_fetched: Optional[float] = None
    fetch_status: str = "pending"  # pending, success, failed
    error_message: str = ""
    
    def __post_init__(self):
        if self.last_fetched is None:
            self.last_fetched = datetime.now().timestamp()

class SitemapAnalyzer:
    """网站地图分析器"""
    
    # 常见的网站地图位置
    COMMON_SITEMAP_LOCATIONS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap/sitemap.xml",
        "/sitemap.xml.gz",  # 压缩格式
        "/sitemap1.xml",
        "/sitemap-0.xml",
        "/sitemap.php",
        "/sitemap.txt",
        "/sitemap/sitemap.txt",
        "/sitemap/sitemap_index.xml",
        "/sitemap/index.xml",
        "/post-sitemap.xml",  # WordPress常见
        "/page-sitemap.xml",
        "/category-sitemap.xml",
        "/tag-sitemap.xml"
    ]
    
    # 网站地图命名空间
    SITEMAP_NS = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1',
        'video': 'http://www.google.com/schemas/sitemap-video/1.1',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None,
                 timeout: float = 30.0, max_recursion_depth: int = 3):
        """
        初始化网站地图分析器
        
        Args:
            session: aiohttp会话（如果为None则创建临时会话）
            timeout: 请求超时时间
            max_recursion_depth: 最大递归深度（用于sitemap索引）
        """
        self.session = session
        self.timeout = timeout
        self.max_recursion_depth = max_recursion_depth
        
        # 缓存
        self.sitemap_cache: Dict[str, SitemapInfo] = {}
        self.url_cache: Dict[str, SitemapURL] = {}
        
        # 统计
        self.stats = {
            'sitemaps_fetched': 0,
            'sitemaps_failed': 0,
            'urls_discovered': 0,
            'unique_domains': set(),
            'start_time': datetime.now().timestamp()
        }
        
        logger.info(f"网站地图分析器初始化完成，最大递归深度: {max_recursion_depth}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def discover_sitemaps(self, base_url: str) -> List[SitemapInfo]:
        """
        发现网站的所有sitemap文件
        
        Args:
            base_url: 基础URL
            
        Returns:
            sitemap信息列表
        """
        sitemaps = []
        
        # 1. 从robots.txt中发现sitemap
        robots_sitemaps = await self._discover_sitemaps_from_robots(base_url)
        sitemaps.extend(robots_sitemaps)
        
        # 2. 尝试常见位置
        common_sitemaps = await self._discover_sitemaps_from_common_locations(base_url)
        sitemaps.extend(common_sitemaps)
        
        # 3. 去重
        unique_sitemaps = self._deduplicate_sitemaps(sitemaps)
        
        logger.info(f"发现 {len(unique_sitemaps)} 个网站地图")
        
        return unique_sitemaps
    
    async def _discover_sitemaps_from_robots(self, base_url: str) -> List[SitemapInfo]:
        """从robots.txt中发现sitemap"""
        sitemaps = []
        
        try:
            robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
            
            async with aiohttp.ClientSession() as temp_session:
                async with temp_session.get(robots_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.lower().startswith('sitemap:'):
                                sitemap_url = line.split(':', 1)[1].strip()
                                
                                sitemap_info = SitemapInfo(
                                    url=sitemap_url,
                                    content_type="unknown",
                                    fetch_status="pending"
                                )
                                sitemaps.append(sitemap_info)
                                
                                logger.debug(f"从robots.txt中发现sitemap: {sitemap_url}")
            
        except Exception as e:
            logger.debug(f"从robots.txt中发现sitemap失败: {e}")
        
        return sitemaps
    
    async def _discover_sitemaps_from_common_locations(self, base_url: str) -> List[SitemapInfo]:
        """从常见位置发现sitemap"""
        sitemaps = []
        
        tasks = []
        for location in self.COMMON_SITEMAP_LOCATIONS:
            sitemap_url = urllib.parse.urljoin(base_url, location)
            tasks.append(self._check_sitemap_exists(sitemap_url))
        
        # 并发检查
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, SitemapInfo):
                sitemaps.append(result)
        
        return sitemaps
    
    async def _check_sitemap_exists(self, url: str) -> SitemapInfo:
        """检查sitemap是否存在"""
        sitemap_info = SitemapInfo(url=url, fetch_status="pending")
        
        try:
            session = self.session or aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            async with session.get(url, allow_redirects=True) as response:
                sitemap_info.last_fetched = datetime.now().timestamp()
                
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    # 判断内容类型
                    if 'xml' in content_type or url.endswith('.xml'):
                        sitemap_info.content_type = "xml"
                    elif 'text/plain' in content_type or url.endswith('.txt'):
                        sitemap_info.content_type = "txt"
                    elif 'html' in content_type:
                        sitemap_info.content_type = "html"
                    else:
                        # 根据内容猜测类型
                        text = await response.text(errors='ignore')
                        if text.strip().startswith('<?xml'):
                            sitemap_info.content_type = "xml"
                        elif '\n' in text and ('http://' in text or 'https://' in text):
                            sitemap_info.content_type = "txt"
                        else:
                            sitemap_info.content_type = "unknown"
                    
                    sitemap_info.fetch_status = "success"
                    self.stats['sitemaps_fetched'] += 1
                    
                    logger.debug(f"Sitemap存在: {url} ({sitemap_info.content_type})")
                    
                else:
                    sitemap_info.fetch_status = "failed"
                    sitemap_info.error_message = f"HTTP {response.status}"
                    self.stats['sitemaps_failed'] += 1
            
        except asyncio.TimeoutError:
            sitemap_info.fetch_status = "failed"
            sitemap_info.error_message = "请求超时"
            self.stats['sitemaps_failed'] += 1
        except aiohttp.ClientError as e:
            sitemap_info.fetch_status = "failed"
            sitemap_info.error_message = f"客户端错误: {e}"
            self.stats['sitemaps_failed'] += 1
        except Exception as e:
            sitemap_info.fetch_status = "failed"
            sitemap_info.error_message = f"未知错误: {e}"
            self.stats['sitemaps_failed'] += 1
        
        finally:
            if not self.session and 'session' in locals():
                await session.close()
        
        return sitemap_info
    
    def _deduplicate_sitemaps(self, sitemaps: List[SitemapInfo]) -> List[SitemapInfo]:
        """去重sitemap（基于URL）"""
        unique_sitemaps = []
        seen_urls = set()
        
        for sitemap in sitemaps:
            normalized_url = self._normalize_url(sitemap.url)
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_sitemaps.append(sitemap)
        
        return unique_sitemaps
    
    async def parse_sitemap(self, sitemap_url: str, depth: int = 0) -> List[SitemapURL]:
        """
        解析sitemap文件（支持递归解析索引）
        
        Args:
            sitemap_url: sitemap URL
            depth: 当前递归深度
            
        Returns:
            URL信息列表
        """
        if depth >= self.max_recursion_depth:
            logger.warning(f"达到最大递归深度 {depth}，停止解析 {sitemap_url}")
            return []
        
        # 检查缓存
        if sitemap_url in self.sitemap_cache:
            cached_info = self.sitemap_cache[sitemap_url]
            if cached_info.fetch_status == "success":
                logger.debug(f"使用缓存的sitemap: {sitemap_url}")
                # 从缓存中获取URL
                return [url for url in self.url_cache.values() 
                       if url.sitemap_source == sitemap_url]
        
        logger.info(f"解析sitemap [{depth}]: {sitemap_url}")
        
        try:
            session = self.session or aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    logger.warning(f"Sitemap获取失败: HTTP {response.status}")
                    return []
                
                content = await response.text()
                content_type = response.headers.get('Content-Type', '').lower()
                
                # 判断内容类型并解析
                if 'xml' in content_type or sitemap_url.endswith('.xml') or content.strip().startswith('<?xml'):
                    urls = await self._parse_xml_sitemap(content, sitemap_url, depth)
                elif 'text/plain' in content_type or sitemap_url.endswith('.txt'):
                    urls = await self._parse_text_sitemap(content, sitemap_url)
                elif 'html' in content_type or sitemap_url.endswith('.html'):
                    urls = await self._parse_html_sitemap(content, sitemap_url)
                else:
                    # 尝试自动检测
                    if content.strip().startswith('<?xml'):
                        urls = await self._parse_xml_sitemap(content, sitemap_url, depth)
                    elif '\n' in content and ('http://' in content or 'https://' in content):
                        urls = await self._parse_text_sitemap(content, sitemap_url)
                    else:
                        logger.warning(f"未知的sitemap格式: {sitemap_url}")
                        urls = []
                
                # 更新缓存
                sitemap_info = SitemapInfo(
                    url=sitemap_url,
                    content_type=content_type,
                    url_count=len(urls),
                    is_index=any(url.sitemap_source != sitemap_url for url in urls),
                    last_fetched=datetime.now().timestamp(),
                    fetch_status="success"
                )
                self.sitemap_cache[sitemap_url] = sitemap_info
                
                # 缓存URL
                for url in urls:
                    self.url_cache[url.url] = url
                
                self.stats['urls_discovered'] += len(urls)
                
                return urls
        
        except Exception as e:
            logger.error(f"解析sitemap失败 {sitemap_url}: {e}")
            
            # 更新缓存（失败状态）
            sitemap_info = SitemapInfo(
                url=sitemap_url,
                content_type="unknown",
                url_count=0,
                is_index=False,
                last_fetched=datetime.now().timestamp(),
                fetch_status="failed",
                error_message=str(e)
            )
            self.sitemap_cache[sitemap_url] = sitemap_info
            
            return []
        
        finally:
            if not self.session and 'session' in locals():
                await session.close()
    
    async def _parse_xml_sitemap(self, xml_content: str, sitemap_url: str, 
                                depth: int) -> List[SitemapURL]:
        """解析XML格式的sitemap"""
        urls = []
        
        try:
            # 解析XML
            root = ET.fromstring(xml_content)
            
            # 检查命名空间
            ns = self._detect_namespace(root)
            
            # 检查是否是sitemap索引
            if root.tag.endswith('sitemapindex') or f'{{{ns}}}sitemapindex' in root.tag:
                # 这是sitemap索引，需要递归解析子sitemap
                child_sitemaps = []
                
                # 查找所有子sitemap
                for sitemap_elem in root.findall('.//{*}sitemap/{*}loc'):
                    child_url = sitemap_elem.text
                    if child_url:
                        child_sitemaps.append(child_url)
                
                logger.info(f"发现sitemap索引，包含 {len(child_sitemaps)} 个子sitemap")
                
                # 递归解析子sitemap
                tasks = [self.parse_sitemap(child_url, depth + 1) 
                        for child_url in child_sitemaps]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 合并结果
                for result in results:
                    if isinstance(result, list):
                        urls.extend(result)
                
            else:
                # 普通sitemap，解析URL
                for url_elem in root.findall('.//{*}url'):
                    loc_elem = url_elem.find('{*}loc')
                    if loc_elem is not None and loc_elem.text:
                        sitemap_url_obj = SitemapURL(
                            url=loc_elem.text,
                            sitemap_source=sitemap_url
                        )
                        
                        # 解析可选字段
                        lastmod_elem = url_elem.find('{*}lastmod')
                        if lastmod_elem is not None and lastmod_elem.text:
                            sitemap_url_obj.lastmod = lastmod_elem.text
                        
                        changefreq_elem = url_elem.find('{*}changefreq')
                        if changefreq_elem is not None and changefreq_elem.text:
                            sitemap_url_obj.changefreq = changefreq_elem.text
                        
                        priority_elem = url_elem.find('{*}priority')
                        if priority_elem is not None and priority_elem.text:
                            try:
                                sitemap_url_obj.priority = float(priority_elem.text)
                            except ValueError:
                                pass
                        
                        urls.append(sitemap_url_obj)
        
        except ET.ParseError as e:
            logger.error(f"XML解析错误: {e}")
            # 尝试作为文本解析
            urls = await self._parse_text_sitemap(xml_content, sitemap_url)
        
        return urls
    
    def _detect_namespace(self, root: ET.Element) -> str:
        """检测XML命名空间"""
        # 检查是否有命名空间
        if '}' in root.tag:
            ns = root.tag.split('}')[0].strip('{')
            return ns
        
        # 尝试从属性中检测
        for key, value in root.attrib.items():
            if 'schema' in key.lower() and 'sitemap' in value.lower():
                return value
        
        # 默认命名空间
        return self.SITEMAP_NS['sm']
    
    async def _parse_text_sitemap(self, text_content: str, sitemap_url: str) -> List[SitemapURL]:
        """解析文本格式的sitemap"""
        urls = []
        
        for line in text_content.split('\n'):
            line = line.strip()
            if line and (line.startswith('http://') or line.startswith('https://')):
                sitemap_url_obj = SitemapURL(
                    url=line,
                    sitemap_source=sitemap_url
                )
                urls.append(sitemap_url_obj)
        
        return urls
    
    async def _parse_html_sitemap(self, html_content: str, sitemap_url: str) -> List[SitemapURL]:
        """解析HTML格式的sitemap"""
        urls = []
        
        # 使用正则表达式提取链接
        link_pattern = r'href=["\']([^"\']+)["\']'
        
        for match in re.finditer(link_pattern, html_content, re.IGNORECASE):
            href = match.group(1)
            
            # 跳过锚点、javascript等
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # 转换为绝对URL
            try:
                absolute_url = urllib.parse.urljoin(sitemap_url, href)
                
                sitemap_url_obj = SitemapURL(
                    url=absolute_url,
                    sitemap_source=sitemap_url
                )
                urls.append(sitemap_url_obj)
            except Exception as e:
                logger.debug(f"URL转换失败 {href}: {e}")
        
        return urls
    
    def _normalize_url(self, url: str) -> str:
        """规范化URL"""
        try:
            parsed = urllib.parse.urlparse(url)
            
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
        except Exception:
            return url.lower()
    
    def filter_urls(self, urls: List[SitemapURL], 
                   filters: Optional[Dict[str, Any]] = None) -> List[SitemapURL]:
        """
        过滤URL
        
        Args:
            urls: URL列表
            filters: 过滤条件字典，支持:
                - min_priority: 最小优先级
                - exclude_patterns: 排除模式列表
                - include_patterns: 包含模式列表
                - max_age_days: 最大天数（基于lastmod）
                - domain_only: 只包含指定域名的URL
                
        Returns:
            过滤后的URL列表
        """
        if not filters:
            return urls
        
        filtered_urls = []
        
        for url_obj in urls:
            include = True
            
            # 检查优先级
            min_priority = filters.get('min_priority')
            if min_priority is not None and url_obj.priority is not None:
                if url_obj.priority < min_priority:
                    include = False
            
            # 检查排除模式
            exclude_patterns = filters.get('exclude_patterns', [])
            for pattern in exclude_patterns:
                if pattern and pattern in url_obj.url:
                    include = False
                    break
            
            # 检查包含模式
            include_patterns = filters.get('include_patterns', [])
            if include_patterns:
                matched = False
                for pattern in include_patterns:
                    if pattern and pattern in url_obj.url:
                        matched = True
                        break
                if not matched:
                    include = False
            
            # 检查域名
            domain_only = filters.get('domain_only')
            if domain_only and url_obj.domain != domain_only:
                include = False
            
            # 检查最后修改时间
            max_age_days = filters.get('max_age_days')
            if max_age_days and url_obj.lastmod:
                try:
                    lastmod_dt = datetime.fromisoformat(url_obj.lastmod.replace('Z', '+00:00'))
                    age_days = (datetime.now() - lastmod_dt).days
                    if age_days > max_age_days:
                        include = False
                except:
                    pass
            
            if include:
                filtered_urls.append(url_obj)
        
        return filtered_urls
    
    def analyze_url_patterns(self, urls: List[SitemapURL]) -> Dict[str, Any]:
        """分析URL模式"""
        analysis = {
            'total_urls': len(urls),
            'by_domain': defaultdict(int),
            'by_path_pattern': defaultdict(int),
            'by_priority': defaultdict(int),
            'by_changefreq': defaultdict(int),
            'has_lastmod': 0,
            'has_priority': 0,
            'has_changefreq': 0
        }
        
        for url_obj in urls:
            # 域名统计
            analysis['by_domain'][url_obj.domain] += 1
            
            # 路径模式统计
            path = url_obj.path
            if path:
                # 提取路径中的数字模式
                pattern = re.sub(r'\d+', '{id}', path)
                analysis['by_path_pattern'][pattern] += 1
            
            # 优先级统计
            if url_obj.priority is not None:
                analysis['has_priority'] += 1
                priority_group = int(url_obj.priority * 10) / 10  # 0.0, 0.1, ..., 1.0
                analysis['by_priority'][priority_group] += 1
            
            # 更新频率统计
            if url_obj.changefreq:
                analysis['has_changefreq'] += 1
                analysis['by_changefreq'][url_obj.changefreq] += 1
            
            # 最后修改时间统计
            if url_obj.lastmod:
                analysis['has_lastmod'] += 1
        
        return analysis
    
    async def crawl_from_sitemaps(self, base_url: str, 
                                max_urls: int = 1000) -> List[SitemapURL]:
        """
        从网站地图爬取所有URL
        
        Args:
            base_url: 基础URL
            max_urls: 最大URL数量
            
        Returns:
            URL信息列表
        """
        # 1. 发现所有sitemap
        sitemaps = await self.discover_sitemaps(base_url)
        
        # 2. 解析所有sitemap
        all_urls = []
        
        tasks = []
        for sitemap_info in sitemaps:
            if sitemap_info.fetch_status == "success" or sitemap_info.fetch_status == "pending":
                tasks.append(self.parse_sitemap(sitemap_info.url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. 合并结果
        for result in results:
            if isinstance(result, list):
                all_urls.extend(result)
        
        # 4. 去重
        unique_urls = self._deduplicate_urls(all_urls)
        
        # 5. 限制数量
        if len(unique_urls) > max_urls:
            # 按优先级排序
            unique_urls.sort(key=lambda x: x.priority or 0.5, reverse=True)
            unique_urls = unique_urls[:max_urls]
        
        logger.info(f"从网站地图中发现 {len(unique_urls)} 个唯一URL")
        
        return unique_urls
    
    def _deduplicate_urls(self, urls: List[SitemapURL]) -> List[SitemapURL]:
        """去重URL"""
        unique_urls = []
        seen_urls = set()
        
        for url_obj in urls:
            normalized = self._normalize_url(url_obj.url)
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_urls.append(url_obj)
        
        return unique_urls
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        elapsed = datetime.now().timestamp() - self.stats['start_time']
        
        return {
            'sitemaps_fetched': self.stats['sitemaps_fetched'],
            'sitemaps_failed': self.stats['sitemaps_failed'],
            'urls_discovered': self.stats['urls_discovered'],
            'unique_domains': len(self.stats['unique_domains']),
            'elapsed_seconds': elapsed,
            'urls_per_second': self.stats['urls_discovered'] / elapsed if elapsed > 0 else 0,
            'sitemap_cache_size': len(self.sitemap_cache),
            'url_cache_size': len(self.url_cache)
        }
    
    def save_results(self, urls: List[SitemapURL], output_dir: str = "./sitemap_results"):
        """保存结果到文件"""
        import json
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON格式
        json_file = output_path / f"sitemap_urls_{timestamp}.json"
        url_data = []
        for url_obj in urls:
            url_data.append({
                'url': url_obj.url,
                'lastmod': url_obj.lastmod,
                'changefreq': url_obj.changefreq,
                'priority': url_obj.priority,
                'sitemap_source': url_obj.sitemap_source,
                'domain': url_obj.domain,
                'path': url_obj.path
            })
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(url_data, f, indent=2, ensure_ascii=False)
        
        # 保存纯文本URL列表
        txt_file = output_path / f"sitemap_urls_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            for url_obj in urls:
                f.write(f"{url_obj.url}\n")
        
        # 保存统计信息
        stats_file = output_path / f"sitemap_stats_{timestamp}.json"
        stats_data = {
            'total_urls': len(urls),
            'timestamp': timestamp,
            'stats': self.get_stats(),
            'analysis': self.analyze_url_patterns(urls)
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"结果已保存到: {output_path}")
        
        return {
            'json_file': str(json_file),
            'txt_file': str(txt_file),
            'stats_file': str(stats_file)
        }