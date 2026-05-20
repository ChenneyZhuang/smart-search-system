#!/usr/bin/env python3
"""
反反爬系统 - 对抗网站反爬措施
包括代理管理、User-Agent轮换、请求指纹随机化、验证码处理等
"""

import random
import time
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
import logging
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio
import aiohttp
import re

logger = logging.getLogger(__name__)

@dataclass
class UserAgentProfile:
    """User-Agent配置"""
    user_agent: str
    browser_type: str  # chrome, firefox, safari, edge
    browser_version: str
    os_type: str  # windows, macos, linux, ios, android
    os_version: str
    device_type: str  # desktop, mobile, tablet
    language: str = "en-US"
    weight: float = 1.0  # 使用权重
    
    @property
    def headers_template(self) -> Dict[str, str]:
        """获取该User-Agent对应的headers模板"""
        base_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': self.language,
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 根据浏览器类型添加特定headers
        if 'chrome' in self.browser_type.lower():
            base_headers['Sec-Ch-Ua'] = '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"'
            base_headers['Sec-Ch-Ua-Mobile'] = '?0'
            base_headers['Sec-Ch-Ua-Platform'] = '"macOS"'
        
        return base_headers

@dataclass
class ProxyServer:
    """代理服务器"""
    host: str
    port: int
    protocol: str = 'http'  # http, https, socks5
    username: Optional[str] = None
    password: Optional[str] = None
    
    # 性能指标
    success_count: int = 0
    failure_count: int = 0
    total_response_time: float = 0.0
    last_used: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    
    # 状态
    enabled: bool = True
    health_score: float = 100.0  # 健康分数 0-100
    
    def __post_init__(self):
        # 确保端口是整数
        self.port = int(self.port)
    
    @property
    def url(self) -> str:
        """代理URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        else:
            return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        total = self.success_count + self.failure_count
        return self.total_response_time / total if total > 0 else 0.0
    
    def record_success(self, response_time: float):
        """记录成功"""
        self.success_count += 1
        self.total_response_time += response_time
        self.last_used = time.time()
        self.last_success = time.time()
        self.health_score = min(100.0, self.health_score + 5.0)
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_used = time.time()
        self.last_failure = time.time()
        self.health_score = max(0.0, self.health_score - 20.0)
        
        # 如果连续失败太多，暂时禁用
        if self.failure_count >= 10 and self.success_rate < 0.1:
            self.enabled = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'host': self.host,
            'port': self.port,
            'protocol': self.protocol,
            'success_rate': self.success_rate,
            'avg_response_time': self.avg_response_time,
            'health_score': self.health_score,
            'enabled': self.enabled,
            'last_used': self.last_used
        }

@dataclass
class RequestFingerprint:
    """请求指纹（用于随机化请求特征）"""
    headers: Dict[str, str]
    cookies: Dict[str, str] = field(default_factory=dict)
    referer: Optional[str] = None
    accept_encoding: List[str] = field(default_factory=lambda: ['gzip', 'deflate'])
    accept_language: str = "en-US,en;q=0.9"
    connection: str = "keep-alive"
    
    # 时间特征
    request_time_offset: float = 0.0  # 请求时间偏移（秒）
    
    def randomize(self):
        """随机化指纹"""
        # 随机化Accept-Language
        languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-AU,en;q=0.9",
            "en-CA,en;q=0.9",
            "zh-CN,zh;q=0.9",
            "zh-TW,zh;q=0.9",
            "ja-JP,ja;q=0.9",
            "ko-KR,ko;q=0.9"
        ]
        self.accept_language = random.choice(languages)
        
        # 随机化Accept-Encoding
        encodings = [
            ['gzip', 'deflate'],
            ['gzip', 'deflate'],
            ['gzip'],
            ['deflate']
        ]
        self.accept_encoding = random.choice(encodings)
        
        # 随机化Connection
        self.connection = random.choice(['keep-alive', 'close'])
        
        # 随机化Referer（如果允许）
        if random.random() > 0.3:  # 70%的概率添加Referer
            referers = [
                'https://www.google.com/',
                'https://www.bing.com/',
                'https://www.yahoo.com/',
                'https://duckduckgo.com/',
                'https://www.reddit.com/',
                'https://news.ycombinator.com/'
            ]
            self.referer = random.choice(referers)
        
        # 随机化请求时间偏移（-1到+1秒）
        self.request_time_offset = random.uniform(-1.0, 1.0)
    
    def apply_to_headers(self, base_headers: Dict[str, str]) -> Dict[str, str]:
        """将指纹应用到headers"""
        headers = base_headers.copy()
        
        # 更新headers
        if 'Accept-Encoding' in headers:
            headers['Accept-Encoding'] = ', '.join(self.accept_encoding)
        
        if 'Accept-Language' in headers:
            headers['Accept-Language'] = self.accept_language
        
        if 'Connection' in headers:
            headers['Connection'] = self.connection
        
        if self.referer:
            headers['Referer'] = self.referer
        
        # 添加随机headers
        if random.random() > 0.5:
            headers['DNT'] = '1'  # Do Not Track
        
        if random.random() > 0.7:
            headers['Cache-Control'] = random.choice(['max-age=0', 'no-cache'])
        
        return headers

class AntiAntiCrawler:
    """反反爬系统"""
    
    def __init__(self, proxy_config_file: Optional[str] = None,
                 user_agents_file: Optional[str] = None):
        """
        初始化反反爬系统
        
        Args:
            proxy_config_file: 代理配置文件路径
            user_agents_file: User-Agent配置文件路径
        """
        # User-Agent管理
        self.user_agents: List[UserAgentProfile] = []
        self.current_ua_index = 0
        
        # 代理管理
        self.proxies: List[ProxyServer] = []
        self.proxy_enabled = False
        self.proxy_rotation_mode = 'round_robin'  # round_robin, random, best_score
        self.current_proxy_index = 0
        
        # 请求指纹
        self.fingerprint_randomization = True
        
        # 验证码处理
        self.captcha_detection_enabled = True
        self.captcha_solving_enabled = False  # 需要外部服务
        
        # 会话管理
        self.session_cookies: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # 加载配置
        self._load_default_user_agents()
        self._load_default_proxies()
        
        if user_agents_file:
            self._load_user_agents_from_file(user_agents_file)
        
        if proxy_config_file:
            self._load_proxies_from_file(proxy_config_file)
        
        logger.info(f"反反爬系统初始化完成: {len(self.user_agents)}个UA, {len(self.proxies)}个代理")
    
    def _load_default_user_agents(self):
        """加载默认User-Agent"""
        default_agents = [
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                browser_type='chrome',
                browser_version='120.0.0.0',
                os_type='windows',
                os_version='10.0',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                browser_type='firefox',
                browser_version='121.0',
                os_type='windows',
                os_version='10.0',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                browser_type='chrome',
                browser_version='120.0.0.0',
                os_type='macos',
                os_version='10.15.7',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
                browser_type='safari',
                browser_version='17.2',
                os_type='macos',
                os_version='10.15.7',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                browser_type='edge',
                browser_version='120.0.0.0',
                os_type='windows',
                os_version='10.0',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                browser_type='chrome',
                browser_version='120.0.0.0',
                os_type='linux',
                os_version='x86_64',
                device_type='desktop'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
                browser_type='safari',
                browser_version='17.2',
                os_type='ios',
                os_version='17.2',
                device_type='mobile'
            ),
            UserAgentProfile(
                user_agent='Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                browser_type='chrome',
                browser_version='120.0.0.0',
                os_type='android',
                os_version='10',
                device_type='mobile'
            )
        ]
        
        self.user_agents.extend(default_agents)
    
    def _load_default_proxies(self):
        """加载默认代理（通常是空的，需要用户配置）"""
        # 这里可以添加一些公共代理，但通常不推荐
        pass
    
    def _load_user_agents_from_file(self, filepath: str):
        """从文件加载User-Agent"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data.get('user_agents', []):
                profile = UserAgentProfile(
                    user_agent=item['user_agent'],
                    browser_type=item.get('browser_type', 'chrome'),
                    browser_version=item.get('browser_version', ''),
                    os_type=item.get('os_type', ''),
                    os_version=item.get('os_version', ''),
                    device_type=item.get('device_type', 'desktop'),
                    language=item.get('language', 'en-US'),
                    weight=item.get('weight', 1.0)
                )
                self.user_agents.append(profile)
            
            logger.info(f"从文件加载 {len(data.get('user_agents', []))} 个User-Agent")
            
        except Exception as e:
            logger.error(f"加载User-Agent文件失败: {e}")
    
    def _load_proxies_from_file(self, filepath: str):
        """从文件加载代理"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data.get('proxies', []):
                proxy = ProxyServer(
                    host=item['host'],
                    port=item['port'],
                    protocol=item.get('protocol', 'http'),
                    username=item.get('username'),
                    password=item.get('password')
                )
                self.proxies.append(proxy)
            
            if self.proxies:
                self.proxy_enabled = True
            
            logger.info(f"从文件加载 {len(self.proxies)} 个代理")
            
        except Exception as e:
            logger.error(f"加载代理文件失败: {e}")
    
    def get_random_user_agent(self) -> UserAgentProfile:
        """获取随机User-Agent"""
        if not self.user_agents:
            # 回退到默认UA
            return self.user_agents[0] if self.user_agents else None
        
        # 加权随机选择
        weights = [ua.weight for ua in self.user_agents]
        selected = random.choices(self.user_agents, weights=weights, k=1)[0]
        
        return selected
    
    def get_rotated_user_agent(self) -> UserAgentProfile:
        """获取轮换的User-Agent"""
        if not self.user_agents:
            return None
        
        self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)
        return self.user_agents[self.current_ua_index]
    
    def get_headers(self, domain: Optional[str] = None) -> Dict[str, str]:
        """获取随机化的headers"""
        # 选择User-Agent
        ua_profile = self.get_random_user_agent()
        if not ua_profile:
            return {}
        
        # 基础headers
        headers = ua_profile.headers_template
        
        # 如果需要随机化指纹
        if self.fingerprint_randomization:
            fingerprint = RequestFingerprint(headers={})
            fingerprint.randomize()
            headers = fingerprint.apply_to_headers(headers)
        
        # 添加域名的cookies（如果有）
        if domain and domain in self.session_cookies:
            cookies = self.session_cookies[domain]
            if cookies:
                # 将cookies添加到headers
                cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
                headers['Cookie'] = cookie_str
        
        return headers
    
    def get_proxy(self) -> Optional[ProxyServer]:
        """获取代理"""
        if not self.proxy_enabled or not self.proxies:
            return None
        
        # 过滤可用的代理
        available_proxies = [p for p in self.proxies if p.enabled]
        if not available_proxies:
            return None
        
        # 根据轮换模式选择代理
        if self.proxy_rotation_mode == 'round_robin':
            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.current_proxy_index += 1
        
        elif self.proxy_rotation_mode == 'random':
            proxy = random.choice(available_proxies)
        
        elif self.proxy_rotation_mode == 'best_score':
            # 按健康分数排序
            available_proxies.sort(key=lambda p: p.health_score, reverse=True)
            proxy = available_proxies[0]
        
        else:
            proxy = available_proxies[0]
        
        return proxy
    
    def update_proxy_performance(self, proxy: ProxyServer, success: bool, 
                                response_time: float = 0.0):
        """更新代理性能"""
        if success:
            proxy.record_success(response_time)
        else:
            proxy.record_failure()
    
    def add_proxy(self, host: str, port: int, protocol: str = 'http',
                 username: Optional[str] = None, password: Optional[str] = None):
        """添加代理"""
        proxy = ProxyServer(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password
        )
        self.proxies.append(proxy)
        
        if not self.proxy_enabled and len(self.proxies) > 0:
            self.proxy_enabled = True
        
        logger.info(f"添加代理: {proxy.url}")
    
    def remove_proxy(self, host: str, port: int):
        """移除代理"""
        self.proxies = [p for p in self.proxies 
                       if not (p.host == host and p.port == port)]
        logger.info(f"移除代理: {host}:{port}")
    
    def enable_proxy(self, enabled: bool = True):
        """启用/禁用代理"""
        self.proxy_enabled = enabled
        logger.info(f"代理{'启用' if enabled else '禁用'}")
    
    def set_proxy_rotation_mode(self, mode: str):
        """设置代理轮换模式"""
        valid_modes = ['round_robin', 'random', 'best_score']
        if mode in valid_modes:
            self.proxy_rotation_mode = mode
            logger.info(f"设置代理轮换模式: {mode}")
        else:
            logger.warning(f"无效的代理轮换模式: {mode}")
    
    def detect_captcha(self, html: str, url: str) -> bool:
        """检测验证码"""
        if not self.captcha_detection_enabled:
            return False
        
        html_lower = html.lower()
        
        # 常见的验证码关键词
        captcha_keywords = [
            'captcha',
            'recaptcha',
            'hcaptcha',
            'cloudflare',
            'security challenge',
            'are you human',
            'verify you are human',
            'turnstile',
            'challenge page'
        ]
        
        # 检查关键词
        for keyword in captcha_keywords:
            if keyword in html_lower:
                logger.warning(f"检测到验证码: {keyword} (URL: {url})")
                return True
        
        # 检查常见的验证码图片URL模式
        captcha_patterns = [
            r'captcha\.(png|jpg|gif)',
            r'recaptcha/api/',
            r'hcaptcha\.com',
            r'challenge\.cloudflare',
            r'turnstile\.cloudflare'
        ]
        
        for pattern in captcha_patterns:
            if re.search(pattern, html_lower):
                logger.warning(f"检测到验证码模式: {pattern} (URL: {url})")
                return True
        
        # 检查特定的HTML结构
        captcha_selectors = [
            r'<div[^>]*class=[^>]*captcha',
            r'<div[^>]*id=[^>]*captcha',
            r'iframe[^>]*recaptcha',
            r'iframe[^>]*hcaptcha',
            r'data-sitekey=',
            r'data-captcha'
        ]
        
        for selector in captcha_selectors:
            if re.search(selector, html_lower, re.IGNORECASE):
                logger.warning(f"检测到验证码选择器: {selector} (URL: {url})")
                return True
        
        return False
    
    def solve_captcha(self, html: str, url: str) -> Optional[str]:
        """解决验证码（需要外部服务）"""
        if not self.captcha_solving_enabled:
            logger.warning("验证码解决功能未启用")
            return None
        
        # 这里可以集成第三方验证码解决服务
        # 如2captcha, anti-captcha, DeathByCaptcha等
        
        logger.info(f"尝试解决验证码: {url}")
        
        # 暂时返回None，表示需要手动解决
        return None
    
    def update_cookies(self, domain: str, cookies: Dict[str, str]):
        """更新cookies"""
        self.session_cookies[domain].update(cookies)
    
    def get_cookies(self, domain: str) -> Dict[str, str]:
        """获取cookies"""
        return self.session_cookies.get(domain, {}).copy()
    
    def clear_cookies(self, domain: Optional[str] = None):
        """清除cookies"""
        if domain:
            if domain in self.session_cookies:
                del self.session_cookies[domain]
                logger.info(f"清除域名cookies: {domain}")
        else:
            self.session_cookies.clear()
            logger.info("清除所有cookies")
    
    def get_session_for_domain(self, domain: str) -> aiohttp.ClientSession:
        """为域名创建会话（包含适当的headers和代理）"""
        # 获取headers
        headers = self.get_headers(domain)
        
        # 获取代理
        proxy = self.get_proxy()
        proxy_url = proxy.url if proxy else None
        
        # 创建连接器
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=2,
            ttl_dns_cache=300
        )
        
        # 创建会话
        session = aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        # 设置代理（如果需要）
        if proxy_url:
            session._proxy = proxy_url
        
        return session
    
    def health_check_proxies(self):
        """健康检查代理"""
        if not self.proxies:
            return
        
        logger.info(f"开始健康检查 {len(self.proxies)} 个代理")
        
        # 这里可以实现异步的健康检查
        # 暂时只是简单检查
        for proxy in self.proxies:
            if not proxy.enabled and proxy.health_score < 30:
                # 健康分数太低，永久移除
                self.proxies.remove(proxy)
                logger.info(f"移除不健康代理: {proxy.host}:{proxy.port}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'user_agents_count': len(self.user_agents),
            'proxies_count': len(self.proxies),
            'proxy_enabled': self.proxy_enabled,
            'proxy_rotation_mode': self.proxy_rotation_mode,
            'fingerprint_randomization': self.fingerprint_randomization,
            'captcha_detection_enabled': self.captcha_detection_enabled,
            'captcha_solving_enabled': self.captcha_solving_enabled,
            'session_cookies_domains': len(self.session_cookies)
        }
        
        # 代理详情
        if self.proxies:
            proxy_stats = []
            for proxy in self.proxies:
                proxy_stats.append({
                    'host': proxy.host,
                    'port': proxy.port,
                    'success_rate': proxy.success_rate,
                    'health_score': proxy.health_score,
                    'enabled': proxy.enabled
                })
            stats['proxies'] = proxy_stats
        
        return stats
    
    def export_config(self, output_file: str):
        """导出配置"""
        try:
            config = {
                'exported_at': datetime.now().isoformat(),
                'user_agents': [],
                'proxies': [],
                'settings': {
                    'proxy_enabled': self.proxy_enabled,
                    'proxy_rotation_mode': self.proxy_rotation_mode,
                    'fingerprint_randomization': self.fingerprint_randomization
                }
            }
            
            # 导出User-Agent
            for ua in self.user_agents:
                config['user_agents'].append({
                    'user_agent': ua.user_agent,
                    'browser_type': ua.browser_type,
                    'browser_version': ua.browser_version,
                    'os_type': ua.os_type,
                    'os_version': ua.os_version,
                    'device_type': ua.device_type,
                    'language': ua.language,
                    'weight': ua.weight
                })
            
            # 导出代理
            for proxy in self.proxies:
                config['proxies'].append({
                    'host': proxy.host,
                    'port': proxy.port,
                    'protocol': proxy.protocol,
                    'username': proxy.username,
                    'password': proxy.password,
                    'success_rate': proxy.success_rate,
                    'health_score': proxy.health_score
                })
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"导出配置到: {output_file}")
            
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
    
    def get_recommendations(self) -> List[Dict[str, str]]:
        """获取建议"""
        recommendations = []
        
        # 检查User-Agent
        if len(self.user_agents) < 5:
            recommendations.append({
                'type': 'warning',
                'message': 'User-Agent数量较少，建议添加更多',
                'action': 'add_more_user_agents'
            })
        
        # 检查代理
        if self.proxy_enabled and len(self.proxies) < 3:
            recommendations.append({
                'type': 'warning',
                'message': '代理数量较少，可能容易被封',
                'action': 'add_more_proxies'
            })
        
        # 检查不健康的代理
        unhealthy_proxies = [p for p in self.proxies if p.health_score < 30]
        if unhealthy_proxies:
            recommendations.append({
                'type': 'error',
                'message': f'有 {len(unhealthy_proxies)} 个不健康的代理',
                'action': 'remove_unhealthy_proxies'
            })
        
        # 检查验证码检测
        if not self.captcha_detection_enabled:
            recommendations.append({
                'type': 'info',
                'message': '验证码检测未启用',
                'action': 'enable_captcha_detection'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'success',
                'message': '配置正常',
                'action': 'no_action'
            })
        
        return recommendations