#!/usr/bin/env python3
"""
智能搜索API - 统一接口
整合并发爬取、验证、缓存和搜索功能
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import time
import hashlib

# 添加本地模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入组件
try:
    from phase3.parallel.concurrent_crawler import ConcurrentCrawler, CrawlResult
    from phase3.cache.memory_cache import get_global_cache
    from phase2_validation_optimized import SearchResult, OptimizedValidationPipeline
except ImportError as e:
    print(f"⚠️  导入模块失败: {e}")
    print("⚠️  请确保所有组件已就位")
    # 定义简化版本
    @dataclass
    class SearchResult:
        url: str = ""
        title: str = ""
        content: str = ""
        source: str = ""
        quality_score: float = 0.0
        validation_score: float = 0.0
        confidence: float = 0.0
    
    class OptimizedValidationPipeline:
        def process_results(self, results):
            return {"best_result": None, "confidence": 0}

@dataclass
class SearchRequest:
    """搜索请求"""
    query: str = ""           # 搜索词
    url: str = ""             # 直接URL
    search_engine: str = "bing"  # 搜索引擎（默认Bing，验证码最少）
    timeout: float = 30.0     # 总超时时间
    use_cache: bool = True    # 使用缓存
    cache_ttl: int = 3600     # 缓存TTL（秒）
    min_confidence: float = 0.4  # 最小置信度

@dataclass
class SearchResponse:
    """搜索响应"""
    success: bool
    request: SearchRequest
    best_result: Optional[Dict] = None
    all_results: List[Dict] = None
    validation_summary: Optional[Dict] = None
    performance: Dict = None
    error: str = ""
    
    def __post_init__(self):
        if self.all_results is None:
            self.all_results = []
        if self.performance is None:
            self.performance = {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "success": self.success,
            "request": {
                "query": self.request.query,
                "url": self.request.url,
                "search_engine": self.request.search_engine,
                "timeout": self.request.timeout,
                "use_cache": self.request.use_cache,
                "min_confidence": self.request.min_confidence
            },
            "best_result": self.best_result,
            "validation_summary": self.validation_summary,
            "performance": self.performance,
            "error": self.error
        }

class SmartSearchAPI:
    """智能搜索API"""
    
    def __init__(self):
        self.crawler = ConcurrentCrawler()
        self.validator = OptimizedValidationPipeline()
        self.cache = get_global_cache()
        
        # 搜索引擎配置
        self.search_engines = {
            "duckduckgo": "https://duckduckgo.com/html/?q={query}",
            "bing": "https://www.bing.com/search?q={query}",
            "google": "https://www.google.com/search?q={query}",
            "brave": "https://search.brave.com/search?q={query}",
        }
        
        # 引擎优先级（基于测试结果，Bing最可靠）
        self.engine_priority = ["bing", "duckduckgo", "brave", "google"]
        
        # 验证码检测关键词
        self.captcha_keywords = [
            "captcha", "验证码", "challenge", "robot", "bot", 
            "duck", "select all squares", "異常情況", "automated"
        ]
    
    def _generate_cache_key(self, request: SearchRequest) -> str:
        """生成缓存键"""
        key_data = f"{request.query}:{request.url}:{request.search_engine}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"search:{key_hash}"
    
    def _detect_captcha(self, content: str) -> bool:
        """
        检测内容中是否包含验证码提示
        
        Args:
            content: 网页内容
            
        Returns:
            是否检测到验证码
        """
        if not content:
            return False
        
        content_lower = content.lower()
        for keyword in self.captcha_keywords:
            if keyword in content_lower:
                return True
        
        return False
    
    def _build_search_url(self, query: str, engine: str = "bing") -> str:
        """构建搜索URL"""
        if engine not in self.search_engines:
            engine = "bing"
        
        template = self.search_engines[engine]
        encoded_query = query.replace(' ', '+')
        return template.format(query=encoded_query)
    
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        执行搜索（支持引擎fallback和验证码检测）
        
        Args:
            request: 搜索请求
            
        Returns:
            搜索响应
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = self._generate_cache_key(request)
        if request.use_cache:
            cached_result = self.cache.get(cache_key)
            if cached_result:
                elapsed = time.time() - start_time
                cached_result["performance"]["cache_hit"] = True
                cached_result["performance"]["total_time"] = elapsed
                return SearchResponse(**cached_result)
        
        # 情况1: 直接URL（不涉及搜索引擎选择）
        if request.url:
            return await self._search_direct_url(request, start_time, cache_key)
        
        # 情况2: 搜索查询（需要选择搜索引擎）
        if request.query:
            return await self._search_with_engine_fallback(request, start_time, cache_key)
        
        # 既无URL也无查询
        return SearchResponse(
            success=False,
            request=request,
            error="未提供查询词或URL",
            performance={"total_time": time.time() - start_time, "cache_hit": False}
        )
    
    async def _search_direct_url(self, request: SearchRequest, start_time: float, cache_key: str) -> SearchResponse:
        """搜索直接URL"""
        try:
            crawl_results = await asyncio.wait_for(
                self.crawler.crawl(request.url),
                timeout=request.timeout
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            return SearchResponse(
                success=False,
                request=request,
                error=f"爬取超时 ({elapsed:.1f}s)",
                performance={"total_time": elapsed, "cache_hit": False}
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return SearchResponse(
                success=False,
                request=request,
                error=f"爬取异常: {str(e)}",
                performance={"total_time": elapsed, "cache_hit": False}
            )
        
        # 处理结果（与之前相同）
        return await self._process_crawl_results(request, crawl_results, request.url, start_time, cache_key)
    
    async def _search_with_engine_fallback(self, request: SearchRequest, start_time: float, cache_key: str) -> SearchResponse:
        """使用引擎fallback搜索查询"""
        # 确定要尝试的引擎顺序
        if request.search_engine and request.search_engine in self.search_engines:
            # 用户指定了引擎，优先使用该引擎
            engines_to_try = [request.search_engine]
            # 如果失败，再尝试其他引擎
            other_engines = [e for e in self.engine_priority if e != request.search_engine]
            engines_to_try.extend(other_engines)
        else:
            # 使用默认优先级
            engines_to_try = self.engine_priority.copy()
        
        errors = []
        last_response = None
        
        for engine in engines_to_try:
            # 构建URL
            target_url = self._build_search_url(request.query, engine)
            
            print(f"🔍 尝试引擎: {engine} ({target_url[:80]}...)")
            
            try:
                # 执行爬取
                crawl_results = await asyncio.wait_for(
                    self.crawler.crawl(target_url),
                    timeout=min(request.timeout, 20)  # 每个引擎单独超时
                )
                
                # 处理结果
                response = await self._process_crawl_results(
                    request, crawl_results, target_url, start_time, cache_key, engine
                )
                
                # 检查是否成功且无验证码
                if response.success:
                    # 检查验证码
                    best_result = response.best_result
                    if best_result and 'content_preview' in best_result:
                        content = best_result['content_preview'].lower()
                        if self._detect_captcha(content):
                            print(f"⚠️  引擎 {engine} 检测到验证码，尝试下一个...")
                            errors.append(f"{engine}: 验证码检测")
                            last_response = response
                            continue  # 尝试下一个引擎
                    
                    # 成功！
                    # 更新性能信息
                    response.performance["engine_used"] = engine
                    response.performance["engines_tried"] = engines_to_try.index(engine) + 1
                    response.performance["total_engines"] = len(engines_to_try)
                    
                    # 如果使用的不是原始请求的引擎，记录一下
                    if engine != request.search_engine:
                        response.performance["engine_fallback"] = True
                        response.performance["original_engine"] = request.search_engine
                    
                    return response
                else:
                    # 失败，记录错误
                    errors.append(f"{engine}: {response.error}")
                    last_response = response
                    
            except asyncio.TimeoutError:
                errors.append(f"{engine}: 超时")
            except Exception as e:
                errors.append(f"{engine}: {str(e)[:50]}")
            
            # 继续尝试下一个引擎
        
        # 所有引擎都失败
        elapsed = time.time() - start_time
        error_msg = f"所有引擎都失败: {', '.join(errors[:3])}"
        if len(errors) > 3:
            error_msg += f" ... (共{len(errors)}个错误)"
        
        return SearchResponse(
            success=False,
            request=request,
            error=error_msg,
            performance={
                "total_time": elapsed,
                "cache_hit": False,
                "engines_tried": len(engines_to_try),
                "all_failed": True
            }
        )
    
    async def _process_crawl_results(self, request: SearchRequest, crawl_results, target_url: str, 
                                   start_time: float, cache_key: str, engine_used: str = None) -> SearchResponse:
        """处理爬取结果（通用逻辑）"""
        # 转换为SearchResult对象
        search_results = []
        for crawl_result in crawl_results:
            if not crawl_result.success:
                continue
            
            data = crawl_result.data
            
            # 提取内容
            content = data.get("content") or data.get("contentPreview") or ""
            
            result = SearchResult(
                url=data.get("url", target_url),
                title=data.get("title", "")[:200],
                content=content[:5000],
                source=crawl_result.source,
                metadata={
                    "elapsed": crawl_result.elapsed,
                    "crawl_success": True
                }
            )
            search_results.append(result)
        
        # 验证结果
        validation_result = self.validator.process_results(search_results)
        
        # 构建响应
        elapsed = time.time() - start_time
        
        response = SearchResponse(
            success=True,
            request=request,
            best_result=validation_result.get("best_result"),
            all_results=validation_result.get("all_results", []),
            validation_summary=validation_result.get("validation_summary"),
            performance={
                "total_time": elapsed,
                "cache_hit": False,
                "crawl_results": len(crawl_results),
                "valid_results": len(search_results),
                "target_url": target_url,
                "engine_used": engine_used or request.search_engine
            }
        )
        
        # 检查置信度
        confidence = validation_result.get("confidence", 0)
        if confidence < request.min_confidence:
            response.success = False
            response.error = f"置信度过低 ({confidence:.3f} < {request.min_confidence})"
        
        # 缓存结果（只有在成功且没有验证码时才缓存）
        if request.use_cache and response.success:
            # 检查验证码
            best_result = response.best_result
            if best_result and 'content_preview' in best_result:
                content = best_result['content_preview'].lower()
                if not self._detect_captcha(content):  # 没有验证码才缓存
                    cache_data = response.to_dict()
                    self.cache.set(cache_key, cache_data, ttl=request.cache_ttl)
                    response.performance["cached"] = True
            else:
                # 没有内容预览，也缓存
                cache_data = response.to_dict()
                self.cache.set(cache_key, cache_data, ttl=request.cache_ttl)
                response.performance["cached"] = True
        
        return response
    
    async def search_query(self, query: str, **kwargs) -> SearchResponse:
        """
        搜索查询词（简化接口）
        
        Args:
            query: 搜索词
            **kwargs: 其他参数传递给SearchRequest
            
        Returns:
            搜索响应
        """
        request = SearchRequest(query=query, **kwargs)
        return await self.search(request)
    
    async def search_url(self, url: str, **kwargs) -> SearchResponse:
        """
        搜索URL（简化接口）
        
        Args:
            url: 目标URL
            **kwargs: 其他参数传递给SearchRequest
            
        Returns:
            搜索响应
        """
        request = SearchRequest(url=url, **kwargs)
        return await self.search(request)

def format_response(response: SearchResponse) -> str:
    """格式化响应用于显示"""
    output = []
    
    if response.success:
        output.append("✅ **搜索成功**")
    else:
        output.append(f"❌ **搜索失败**: {response.error}")
    
    output.append("")
    
    # 请求信息
    req = response.request
    output.append("📋 **请求信息**:")
    if req.query:
        output.append(f"   查询: {req.query}")
    if req.url:
        output.append(f"   URL: {req.url}")
    output.append(f"   搜索引擎: {req.search_engine}")
    output.append(f"   超时: {req.timeout}s")
    output.append(f"   使用缓存: {req.use_cache}")
    output.append(f"   最小置信度: {req.min_confidence}")
    
    output.append("")
    
    # 性能信息
    perf = response.performance
    if perf:
        output.append("⚡ **性能信息**:")
        output.append(f"   总耗时: {perf.get('total_time', 0):.1f}s")
        output.append(f"   缓存命中: {perf.get('cache_hit', False)}")
        output.append(f"   爬取结果数: {perf.get('crawl_results', 0)}")
        output.append(f"   有效结果数: {perf.get('valid_results', 0)}")
        
        # 引擎信息
        if 'engine_used' in perf:
            output.append(f"   使用引擎: {perf.get('engine_used')}")
        if 'engines_tried' in perf:
            output.append(f"   尝试引擎数: {perf.get('engines_tried')}/{perf.get('total_engines', '?')}")
        if 'engine_fallback' in perf and perf['engine_fallback']:
            output.append(f"   ⚠️  引擎降级: {perf.get('original_engine', '?')} → {perf.get('engine_used')}")
        if 'cached' in perf:
            output.append(f"   已缓存: {perf.get('cached')}")
    
    output.append("")
    
    # 最佳结果
    best = response.best_result
    if best:
        output.append("🏆 **最佳结果**:")
        output.append(f"   来源: {best.get('source', '未知')}")
        output.append(f"   标题: {best.get('title', '无标题')}")
        output.append(f"   验证评分: {best.get('validation_score', 0)}/100")
        output.append(f"   置信度: {best.get('confidence', 0):.3f}")
        
        if 'content_preview' in best:
            output.append(f"   内容预览: {best['content_preview']}")
    
    # 验证摘要
    summary = response.validation_summary
    if summary:
        output.append("")
        output.append("📊 **验证摘要**:")
        output.append(f"   总结果数: {summary.get('total_results', 0)}")
        output.append(f"   成功结果: {summary.get('successful_results', 0)}")
        output.append(f"   失败结果: {summary.get('failed_results', 0)}")
        
        if 'consistency_rate' in summary:
            output.append(f"   一致性率: {summary['consistency_rate']:.2f}")
    
    return "\n".join(output)

async def test_api():
    """测试API"""
    print("🧪 测试智能搜索API")
    print("=" * 60)
    
    api = SmartSearchAPI()
    
    # 测试1: URL搜索
    print("\n1. 🔗 URL搜索测试...")
    request = SearchRequest(
        url="https://example.com",
        use_cache=False,
        min_confidence=0.3
    )
    
    response = await api.search(request)
    print(format_response(response))
    
    # 测试2: 查询搜索（DuckDuckGo）
    print("\n2. 🔍 查询搜索测试...")
    response = await api.search_query(
        query="OpenClaw AI",
        search_engine="duckduckgo",
        use_cache=False,
        min_confidence=0.3
    )
    print(format_response(response))
    
    # 测试3: 缓存测试
    print("\n3. 💾 缓存测试...")
    start_time = time.time()
    response1 = await api.search_query("test cache", use_cache=True)
    elapsed1 = time.time() - start_time
    
    start_time = time.time()
    response2 = await api.search_query("test cache", use_cache=True)
    elapsed2 = time.time() - start_time
    
    print(f"   第一次: {elapsed1:.2f}s (缓存设置)")
    print(f"   第二次: {elapsed2:.2f}s (缓存读取)")
    print(f"   缓存命中: {response2.performance.get('cache_hit', False)}")
    
    # 显示缓存统计
    stats = api.cache.stats()
    print(f"\n📊 缓存统计:")
    print(f"   总条目: {stats['total_entries']}")
    print(f"   有效条目: {stats['valid_entries']}")
    print(f"   过期条目: {stats['expired_entries']}")
    
    return response.success

async def main():
    """主函数"""
    print("🤖 智能搜索API v1.0")
    print("=" * 60)
    print("组件: 并发爬取器 + 验证系统 + 内存缓存")
    print("搜索引擎: DuckDuckGo (默认), Bing, Google, Brave")
    print("=" * 60)
    
    try:
        await test_api()
        print("\n🎉 API测试完成!")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())