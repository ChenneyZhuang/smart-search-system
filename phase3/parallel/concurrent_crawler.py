#!/usr/bin/env python3
"""
并行爬取框架
同时执行多个爬取方案，返回最快有效结果
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import time
import subprocess

# 尝试导入aiohttp，如果不可用则禁用HTTP策略
try:
    import aiohttp
    import aiohttp.client_exceptions
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# 尝试导入高级HTTP连接池（深度优化）
try:
    from phase4.optimization.advanced_http_pool import get_global_http_pool
    ADVANCED_HTTP_POOL_AVAILABLE = True
except ImportError:
    ADVANCED_HTTP_POOL_AVAILABLE = False

@dataclass
class CrawlResult:
    """爬取结果"""
    source: str  # 方案名称
    success: bool
    data: Dict = None
    error: str = ""
    elapsed: float = 0.0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.data is None:
            self.data = {}

class CrawlStrategy:
    """爬取策略基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.timeout = 30  # 默认超时
    
    async def execute(self, url: str) -> CrawlResult:
        """执行爬取"""
        raise NotImplementedError

class PlaywrightSimpleStrategy(CrawlStrategy):
    """playwright-simple.js策略"""
    
    def __init__(self):
        super().__init__("playwright_simple")
        self.timeout = 25  # 增加超时时间
        self.script_path = "/Volumes/SSD/skills/playwright-scraper-skill/scripts/playwright-simple.js"
    
    async def execute(self, url: str) -> CrawlResult:
        start_time = time.time()
        
        try:
            # 运行Node.js脚本
            cmd = ["node", self.script_path, url]
            
            # 在playwright目录运行
            cwd = "/Volumes/SSD/skills/playwright-scraper-skill"
            
            # 异步执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
                
                elapsed = time.time() - start_time
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')[:200]
                    return CrawlResult(
                        source=self.name,
                        success=False,
                        error=f"脚本失败: {error_msg}",
                        elapsed=elapsed
                    )
                
                # 解析输出
                output = stdout.decode('utf-8', errors='ignore')
                
                # 提取JSON
                data = self._extract_json(output)
                if not data:
                    return CrawlResult(
                        source=self.name,
                        success=False,
                        error="无法解析JSON输出",
                        elapsed=elapsed,
                        metadata={"raw_output": output[:500]}
                    )
                
                return CrawlResult(
                    source=self.name,
                    success=True,
                    data=data,
                    elapsed=elapsed
                )
                
            except asyncio.TimeoutError:
                # 超时，终止进程
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                
                return CrawlResult(
                    source=self.name,
                    success=False,
                    error=f"超时 ({self.timeout}秒)",
                    elapsed=self.timeout
                )
                
        except Exception as e:
            elapsed = time.time() - start_time
            return CrawlResult(
                source=self.name,
                success=False,
                error=f"执行异常: {str(e)}",
                elapsed=elapsed
            )
    
    def _extract_json(self, output: str) -> Optional[Dict]:
        """从输出中提取JSON"""
        if not output:
            return None
        
        start = output.find('{')
        end = output.rfind('}')
        
        if start == -1 or end == -1 or end <= start:
            return None
        
        json_str = output[start:end+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试修复
            json_str = json_str.strip()
            if json_str.endswith(',}'):
                json_str = json_str[:-2] + '}'
            try:
                return json.loads(json_str)
            except:
                return None

class PlaywrightStealthStrategy(CrawlStrategy):
    """playwright-stealth.js策略"""
    
    def __init__(self):
        super().__init__("playwright_stealth")
        self.timeout = 35  # 增加超时时间
        self.script_path = "/Volumes/SSD/skills/playwright-scraper-skill/scripts/playwright-stealth.js"
    
    async def execute(self, url: str) -> CrawlResult:
        start_time = time.time()
        
        try:
            # 运行Node.js脚本
            cmd = ["node", self.script_path, url]
            
            # 环境变量
            env = os.environ.copy()
            env["HEADLESS"] = "true"
            env["WAIT_TIME"] = "5000"
            
            # 在playwright目录运行
            cwd = "/Volumes/SSD/skills/playwright-scraper-skill"
            
            # 异步执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
                
                elapsed = time.time() - start_time
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')[:200]
                    return CrawlResult(
                        source=self.name,
                        success=False,
                        error=f"脚本失败: {error_msg}",
                        elapsed=elapsed
                    )
                
                # 解析输出
                output = stdout.decode('utf-8', errors='ignore')
                
                # 提取JSON
                data = self._extract_json(output)
                if not data:
                    return CrawlResult(
                        source=self.name,
                        success=False,
                        error="无法解析JSON输出",
                        elapsed=elapsed,
                        metadata={"raw_output": output[:500]}
                    )
                
                return CrawlResult(
                    source=self.name,
                    success=True,
                    data=data,
                    elapsed=elapsed
                )
                
            except asyncio.TimeoutError:
                # 超时，终止进程
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                
                return CrawlResult(
                    source=self.name,
                    success=False,
                    error=f"超时 ({self.timeout}秒)",
                    elapsed=self.timeout
                )
                
        except Exception as e:
            elapsed = time.time() - start_time
            return CrawlResult(
                source=self.name,
                success=False,
                error=f"执行异常: {str(e)}",
                elapsed=elapsed
            )
    
    def _extract_json(self, output: str) -> Optional[Dict]:
        """从输出中提取JSON"""
        if not output:
            return None
        
        start = output.find('{')
        end = output.rfind('}')
        
        if start == -1 or end == -1 or end <= start:
            return None
        
        json_str = output[start:end+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试修复
            json_str = json_str.strip()
            if json_str.endswith(',}'):
                json_str = json_str[:-2] + '}'
            try:
                return json.loads(json_str)
            except:
                return None

class HttpFastStrategy(CrawlStrategy):
    """快速HTTP策略（使用aiohttp）"""
    
    def __init__(self):
        super().__init__("http_fast")
        self.timeout = 20  # 增加超时时间，搜索引擎可能较慢
        self.max_retries = 2  # 最大重试次数
        self.session = None  # 延迟初始化
        self.use_advanced_pool = False
        self.advanced_pool = None
        
        # 如果高级HTTP连接池可用，优先使用
        if ADVANCED_HTTP_POOL_AVAILABLE:
            self.use_advanced_pool = True
            print(f"✅ HTTP策略: 启用高级连接池")
        else:
            print(f"⚠️  HTTP策略: 高级连接池不可用，使用标准aiohttp")
    
    async def _get_session(self):
        """获取或创建aiohttp会话"""
        if self.use_advanced_pool and self.advanced_pool is None:
            # 初始化高级HTTP连接池
            try:
                self.advanced_pool = await get_global_http_pool()
                return None  # 高级连接池返回None，我们直接使用pool.request
            except Exception as e:
                print(f"⚠️  高级HTTP连接池初始化失败: {e}")
                self.use_advanced_pool = False
        
        if not self.use_advanced_pool and self.session is None:
            # 创建标准aiohttp会话
            connector = aiohttp.TCPConnector(
                limit=10,  # 连接池大小
                limit_per_host=5,  # 每主机连接数
                ttl_dns_cache=300,  # DNS缓存TTL
                enable_cleanup_closed=True
            )
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._get_headers()
            )
        return self.session
    
    def _get_headers(self) -> Dict:
        """获取HTTP请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'DNT': '1',
        }
    
    async def execute(self, url: str) -> CrawlResult:
        """执行HTTP请求（支持重试）"""
        start_time = time.time()
        
        # 检查aiohttp是否可用
        if not AIOHTTP_AVAILABLE:
            return CrawlResult(
                source=self.name,
                success=False,
                error="aiohttp不可用",
                elapsed=time.time() - start_time
            )
        
        last_error = None
        last_response = None
        
        # 重试逻辑
        for retry in range(self.max_retries + 1):
            attempt_start = time.time()
            
            # 如果不是第一次尝试，添加随机延迟（1-3秒）
            if retry > 0:
                import random
                delay = 1 + random.random() * 2  # 1-3秒
                await asyncio.sleep(delay)
            
            try:
                response = None
                request_kwargs = {
                    'allow_redirects': True,
                    'ssl': False,
                }
                
                # 如果是搜索引擎URL，添加更多参数
                if any(engine in url.lower() for engine in ['bing.com', 'duckduckgo.com', 'google.com']):
                    request_kwargs.update({
                        'headers': {
                            'Referer': 'https://www.google.com/',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        }
                    })
                
                if self.use_advanced_pool and self.advanced_pool:
                    # 使用高级HTTP连接池
                    # 注意：高级连接池的request方法需要传递所有参数
                    response = await self.advanced_pool.request('GET', url, **request_kwargs)
                else:
                    # 使用标准aiohttp会话
                    session = await self._get_session()
                    response = await session.get(url, **request_kwargs)
                
                # 处理响应（高级连接池和标准会话共享相同逻辑）
                if response:
                    attempt_elapsed = time.time() - attempt_start
                    last_response = response
                    
                    # 检查状态码
                    if response.status == 200:
                        # 读取内容
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                            last_error = f"非HTML内容: {content_type[:30]}"
                            continue  # 重试
                        
                        html = await response.text()
                        
                        # 检查是否有验证码或反爬虫页面
                        if self._is_blocked_page(html, url):
                            last_error = "检测到反爬虫页面"
                            continue  # 重试
                        
                        # 简单解析HTML（简化版）
                        result_data = self._parse_html(html, url)
                        
                        # 检查结果是否有效
                        if not result_data.get('title') and not result_data.get('contentPreview'):
                            last_error = "页面内容解析失败"
                            continue  # 重试
                        
                        total_elapsed = time.time() - start_time
                        return CrawlResult(
                            source=self.name,
                            success=True,
                            data=result_data,
                            elapsed=total_elapsed,
                            metadata={"attempts": retry + 1}
                        )
                    elif response.status in [403, 429, 503]:  # 常见反爬虫状态码
                        last_error = f"HTTP {response.status} (反爬虫)"
                        continue  # 重试
                    else:
                        last_error = f"HTTP {response.status}"
                        # 4xx错误通常不会在重试后改变
                        if 400 <= response.status < 500:
                            break
                        continue  # 重试
                else:
                    last_error = "未获取到响应对象"
                    continue  # 重试
                        
            except asyncio.TimeoutError:
                last_error = f"HTTP请求超时 (尝试 {retry + 1})"
                continue  # 重试
            except aiohttp.client_exceptions.ClientError as e:
                last_error = f"HTTP客户端错误: {str(e)[:100]}"
                continue  # 重试
            except Exception as e:
                last_error = f"HTTP请求异常: {str(e)[:100]}"
                continue  # 重试
        
        # 所有重试都失败
        total_elapsed = time.time() - start_time
        error_msg = last_error or "未知错误"
        
        # 如果最后一次有响应，添加状态码信息
        if last_response:
            error_msg = f"{error_msg} (状态码: {last_response.status})"
        
        return CrawlResult(
            source=self.name,
            success=False,
            error=error_msg,
            elapsed=total_elapsed,
            metadata={"attempts": self.max_retries + 1}
        )
    
    def _is_blocked_page(self, html: str, url: str) -> bool:
        """检查页面是否被反爬虫机制阻止"""
        blocked_indicators = [
            'captcha', '验证码', 'robot', 'bot detected',
            'access denied', 'access blocked', 'rate limit',
            'security check', '安全检查', 'human verification'
        ]
        
        html_lower = html.lower()
        for indicator in blocked_indicators:
            if indicator in html_lower:
                return True
        
        # 检查特定搜索引擎的反爬虫页面
        if 'bing.com' in url:
            if 'bing' in html_lower and ('captcha' in html_lower or 'security check' in html_lower):
                return True
        
        return False
    
    def _parse_html(self, html: str, url: str) -> Dict[str, Any]:
        """简单解析HTML，提取标题和内容"""
        import re
        
        result = {
            'url': url,
            'title': '',
            'contentPreview': '',
            'metadata': {}
        }
        
        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            result['title'] = title_match.group(1).strip()[:200]
        
        # 提取meta描述
        desc_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
        if desc_match:
            result['metadata']['description'] = desc_match.group(1).strip()[:500]
        
        # 提取正文内容（简化版）
        # 移除脚本和样式
        cleaned = re.sub(r'<script.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'<style.*?</style>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'<.*?>', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 取前500个字符作为预览
        if cleaned:
            result['contentPreview'] = cleaned[:500]
        
        return result
    
    async def cleanup(self):
        """清理会话"""
        if self.session:
            await self.session.close()
            self.session = None
        
        if self.use_advanced_pool and self.advanced_pool:
            await self.advanced_pool.close_all()
            self.advanced_pool = None

class ConcurrentCrawler:
    """并发爬取器"""
    
    def __init__(self):
        # 初始化策略列表，HTTP策略优先（如果可用）
        self.strategies = []
        
        # 添加HTTP快速策略（如果可用）
        if AIOHTTP_AVAILABLE:
            self.strategies.append(HttpFastStrategy())
            print(f"✅ HTTP快速策略已启用 (连接池优化)")
        else:
            print(f"⚠️  aiohttp未安装，HTTP快速策略不可用")
        
        # 添加Playwright策略
        self.strategies.extend([
            PlaywrightSimpleStrategy(),
            PlaywrightStealthStrategy(),
        ])
    
    async def cleanup(self):
        """清理所有策略的资源"""
        for strategy in self.strategies:
            if hasattr(strategy, 'cleanup'):
                await strategy.cleanup()
    
    async def crawl(self, url: str, strategy_filter: List[str] = None) -> List[CrawlResult]:
        """
        并发爬取URL
        strategy_filter: 指定使用的策略列表，None表示使用所有策略
        """
        if strategy_filter:
            strategies = [s for s in self.strategies if s.name in strategy_filter]
        else:
            strategies = self.strategies
        
        # 创建所有任务
        tasks = []
        for strategy in strategies:
            task = asyncio.create_task(strategy.execute(url))
            tasks.append((strategy.name, task))
        
        # 等待所有任务完成
        results = []
        for name, task in tasks:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append(CrawlResult(
                    source=name,
                    success=False,
                    error=f"任务异常: {str(e)}",
                    elapsed=0
                ))
        
        return results
    
    async def crawl_fastest(self, url: str, min_quality: float = 0.0) -> Optional[CrawlResult]:
        """
        返回最快有效结果
        min_quality: 最低质量要求（0-1），基于结果特征
        """
        # 创建所有任务
        tasks = []
        for strategy in self.strategies:
            task = asyncio.create_task(strategy.execute(url))
            tasks.append(task)
        
        # 等待第一个成功结果
        while tasks:
            # 等待下一个完成的任务
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 检查完成的任务
            for task in done:
                try:
                    result = task.result()
                    
                    # 检查质量
                    if result.success and self._check_quality(result) >= min_quality:
                        # 取消其他任务
                        for t in pending:
                            t.cancel()
                        return result
                    
                except Exception as e:
                    # 任务异常，继续等待其他任务
                    pass
            
            # 更新任务列表
            tasks = list(pending)
        
        return None
    
    def _check_quality(self, result: CrawlResult) -> float:
        """检查结果质量（简化版）"""
        if not result.success:
            return 0.0
        
        data = result.data
        if not data:
            return 0.0
        
        score = 0.0
        
        # 检查标题
        if data.get('title'):
            score += 0.3
        
        # 检查内容
        content = data.get('content') or data.get('contentPreview', '')
        if content and len(content) > 100:
            score += 0.5
        
        # 检查URL
        if data.get('url'):
            score += 0.2
        
        return min(1.0, score)

async def test_concurrent_crawler():
    """测试并发爬取器"""
    print("🧪 测试并发爬取器")
    print("=" * 50)
    
    crawler = ConcurrentCrawler()
    test_url = "https://example.com"
    
    print(f"测试URL: {test_url}")
    print(f"可用策略: {[s.name for s in crawler.strategies]}")
    
    # 测试并发爬取
    print("\n🔍 并发爬取测试...")
    start_time = time.time()
    results = await crawler.crawl(test_url)
    elapsed = time.time() - start_time
    
    print(f"总耗时: {elapsed:.1f}s")
    print(f"结果数: {len(results)}")
    
    success_count = sum(1 for r in results if r.success)
    print(f"成功数: {success_count}")
    
    for result in results:
        status = "✅" if result.success else "❌"
        print(f"  {status} {result.source}: {result.elapsed:.1f}s")
        if not result.success:
            print(f"     错误: {result.error[:80]}")
    
    # 测试最快结果
    print("\n⚡ 最快结果测试...")
    start_time = time.time()
    fastest = await crawler.crawl_fastest(test_url, min_quality=0.5)
    elapsed = time.time() - start_time
    
    if fastest:
        print(f"找到最快结果 ({elapsed:.1f}s):")
        print(f"  策略: {fastest.source}")
        print(f"  耗时: {fastest.elapsed:.1f}s")
        print(f"  标题: {fastest.data.get('title', '无标题')[:50]}")
    else:
        print("未找到符合质量要求的结果")
    
    return len(results) > 0

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_concurrent_crawler())