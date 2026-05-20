#!/usr/bin/env python3
"""
智能搜索系统 - 阶段2优化版：调整评分标准和阈值
"""

import json
import re
import html
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
import math

@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str = ""
    content: str = ""
    source: str = ""
    quality_score: float = 0.0
    validation_score: float = 0.0
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "title": self.title[:100],
            "content_preview": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "source": self.source,
            "quality_score": round(self.quality_score, 1),
            "validation_score": round(self.validation_score, 1),
            "confidence": round(self.confidence, 3),
            "error_count": len(self.errors),
            "has_content": bool(self.content and len(self.content) > 10)
        }

class TextProcessor:
    """文本处理工具类"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        normalized = TextProcessor.normalize_text(text)
        if not normalized:
            return []
        tokens = normalized.split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        tokens = [t for t in tokens if t not in stop_words and len(t) > 1]
        return tokens
    
    @staticmethod
    def jaccard_similarity(text1: str, text2: str) -> float:
        tokens1 = set(TextProcessor.tokenize(text1))
        tokens2 = set(TextProcessor.tokenize(text2))
        
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union if union > 0 else 0.0

class OptimizedValidator:
    """优化后的验证器（更宽松的标准）"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
    
    def calculate_quality_score(self, result: SearchResult) -> float:
        """计算质量评分（优化版）"""
        score = 0.0
        
        # 1. 标题（15%）
        if result.title and len(result.title) > 1:
            title_len = len(result.title)
            # 标题长度评分：1-50字符得满分
            title_score = min(15, title_len * 0.3)
            score += title_score
        else:
            # 无标题，但这不是致命错误
            pass
        
        # 2. 内容长度（50%）
        if result.content:
            content_len = len(result.content)
            # 内容长度评分：100字符起评，1000字符得满分
            if content_len >= 1000:
                score += 50
            elif content_len >= 100:
                score += min(50, content_len * 0.05)
            else:
                score += content_len * 0.2  # 短内容也有部分分
        else:
            # 无内容，严重扣分
            pass
        
        # 3. URL有效性（15%）
        if result.url and result.url.startswith(('http://', 'https://')):
            score += 15
        
        # 4. 来源可靠性（20%）
        source_scores = {
            "playwright_stealth": 20,
            "playwright_simple": 18,
            "browser_tool": 12,
            "web_fetch": 10
        }
        score += source_scores.get(result.source, 0)
        
        # 额外加分：JSON/结构化数据
        if result.content and ('{' in result.content or '[' in result.content):
            # 可能是API响应，给予额外分数
            try:
                json.loads(result.content)
                score += 10  # 有效JSON
            except:
                # 不是有效JSON，但可能有结构化数据
                if result.content.count('"') > 4:
                    score += 5
        
        return min(100, max(0, score))
    
    def validate_single_result(self, result: SearchResult) -> SearchResult:
        """验证单个结果（优化版）"""
        # 计算质量评分
        result.quality_score = self.calculate_quality_score(result)
        
        # 初始验证评分 = 质量评分
        result.validation_score = result.quality_score
        
        # 检查问题（但不严重扣分）
        if not result.title or len(result.title) < 2:
            result.errors.append("标题过短")
            # 轻微扣分，不是致命
            result.validation_score *= 0.9
        
        if not result.content or len(result.content) < 20:
            result.errors.append("内容过短")
            # 根据场景：API响应可能很短
            if 'json' in result.url or 'api' in result.url:
                result.validation_score *= 0.8  # API内容短是正常的
            else:
                result.validation_score *= 0.6
        
        # 检查错误页面
        if result.content:
            error_patterns = [
                r"404\s+not\s+found",
                r"page\s+not\s+found",
                r"access\s+denied",
                r"forbidden",
                r"error\s+\d+",
                r"異常情況",  # Google反爬提示
                r"自動程式"   # Google反爬提示
            ]
            
            content_lower = result.content.lower()
            for pattern in error_patterns:
                if re.search(pattern, content_lower):
                    result.errors.append(f"检测到错误/反爬: {pattern}")
                    result.validation_score *= 0.3  # 严重扣分
                    break
        
        result.validation_score = min(100, max(0, result.validation_score))
        
        return result
    
    def compare_results(self, result1: SearchResult, result2: SearchResult) -> Dict:
        """比较两个结果"""
        similarities = {
            "title": self.text_processor.jaccard_similarity(result1.title, result2.title),
            "content": self.text_processor.jaccard_similarity(
                result1.content[:500],  # 只比较前500字符
                result2.content[:500]
            )
        }
        
        # 计算平均相似度（加权）
        avg_similarity = (similarities["title"] * 0.4 + similarities["content"] * 0.6)
        
        # 宽松的一致性判断
        is_consistent = avg_similarity > 0.4  # 原为0.6
        
        return {
            "similarities": similarities,
            "average_similarity": avg_similarity,
            "is_consistent": is_consistent,
            "score_difference": abs(result1.validation_score - result2.validation_score)
        }

class OptimizedValidationPipeline:
    """优化后的验证管道 - 支持 Bing/DuckDuckGo/Brave/Google 真实解析"""
    
    def __init__(self, max_results: int = 15):
        self.validator = OptimizedValidator()
        self.max_results = max_results
    
    def _parse_bing(self, html_content: str) -> List[SearchResult]:
        """解析 Bing 搜索结果"""
        results = []
        # Bing 结构: <li class="b_algo"> ... <h2><a href="URL">Title</a></h2> ... <p>Snippet</p> ... </li>
        # 找每个 b_algo 块
        algo_blocks = re.findall(r'<li\s+class="b_algo"[^>]*>(.*?)</li>', html_content, re.DOTALL | re.IGNORECASE)
        
        for block in algo_blocks[:self.max_results]:
            # 提取标题和URL
            title_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
            if not title_match:
                continue
            
            url = title_match.group(1)
            title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
            title = html.unescape(title)
            
            # 提取摘要
            snippet = ''
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL | re.IGNORECASE)
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                snippet = html.unescape(snippet)
            
            # 过滤非http链接
            if not url.startswith('http'):
                continue
            
            # 过滤明显的广告和导航
            if any(bad in url.lower() for bad in ['/ads/', 'doubleclick', 'googlesyndication', 'bing.com/videos']):
                continue
            
            results.append(SearchResult(
                url=url,
                title=title[:200],
                content=snippet[:500],
                source="bing",
                quality_score=85.0,
                validation_score=85.0,
                confidence=0.85,
            ))
        
        return results
    
    def _parse_duckduckgo(self, html_content: str) -> List[SearchResult]:
        """解析 DuckDuckGo HTML 搜索结果 — 直接提取 result__a + result__snippet"""
        results = []
        from urllib.parse import unquote
        
        # 直接提取所有 result__a 链接和对应片段（容许多余属性在class前面）
        links = re.findall(r'<a\s+[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)
        snippets = re.findall(r'<a\s+[^>]*class="result__snippet"[^>]*>(.*?)</a>', html_content, re.DOTALL | re.IGNORECASE)
        
        for i, (raw_url, raw_title) in enumerate(links[:self.max_results]):
            # 过滤广告
            if any(bad in raw_url.lower() for bad in ['ad_domain=', 'ad_provider=', 'bing.com/aclick', 'ad_type=']):
                continue
            
            # 解码 DDG 跳转URL
            url = raw_url
            if 'uddg=' in raw_url:
                uddg_match = re.search(r'uddg=([^&]+)', raw_url)
                if uddg_match:
                    url = unquote(uddg_match.group(1))
            
            if url.startswith('//'):
                url = 'https:' + url
            if not url.startswith('http'):
                continue
            
            title = html.unescape(re.sub(r'<[^>]+>', '', raw_title).strip())
            if not title or len(title) < 2:
                continue
            
            snippet = ''
            if i < len(snippets):
                snippet = html.unescape(re.sub(r'<[^>]+>', '', snippets[i]).strip())
            
            results.append(SearchResult(
                url=url, title=title[:200], content=snippet[:500],
                source="duckduckgo", quality_score=82.0, validation_score=82.0, confidence=0.82,
            ))
        
        return results
    
    def _parse_brave(self, html_content: str) -> List[SearchResult]:
        """解析 Brave Search 结果"""
        results = []
        # Brave: <div class="snippet"> ... <a href="URL">Title</a> ... <p class="snippet-description">Desc</p>
        snippets = re.findall(r'<div\s+class="snippet[^"]*"[^>]*>(.*?)</div>\s*</div>', html_content, re.DOTALL | re.IGNORECASE)
        for block in snippets[:self.max_results]:
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
            if not link_match or not link_match.group(1).startswith('http'):
                continue
            title = html.unescape(re.sub(r'<[^>]+>', '', link_match.group(2)).strip())
            desc_match = re.search(r'class="snippet-description[^"]*"[^>]*>(.*?)</(?:p|div)>', block, re.DOTALL | re.IGNORECASE)
            desc = html.unescape(re.sub(r'<[^>]+>', '', desc_match.group(1) if desc_match else '')).strip()
            results.append(SearchResult(
                url=link_match.group(1), title=title[:200], content=desc[:500],
                source="brave", quality_score=82.0, validation_score=82.0, confidence=0.82
            ))
        return results
    
    def _parse_google(self, html_content: str) -> List[SearchResult]:
        """解析 Google 搜索结果 (basic)"""
        results = []
        # Google: <a href="URL" jsname="..."><h3>Title</h3></a> ... <div class="VwiC3b">Snippet</div>
        links = re.findall(r'<a\s+href="(/url\?q=|)(https?://[^"&]+)', html_content, re.IGNORECASE)
        seen = set()
        for _, url in links[:self.max_results]:
            if url in seen:
                continue
            seen.add(url)
            results.append(SearchResult(
                url=url, title=url.split('/')[2],
                content=f"Google search result for: {url}",
                source="google", quality_score=75.0, validation_score=75.0, confidence=0.70
            ))
        return results
    
    def validate(self, content: str, query: str) -> List[SearchResult]:
        """验证HTML内容并提取搜索结果 - 自动检测搜索引擎"""
        if not content or len(content) < 100:
            return []
        
        # 自动检测搜索引擎（扫更多内容，DDG的结果可能在前500字符之后）
        content_lower = content[:3000].lower()
        if 'class="b_algo"' in content_lower or 'bing.com/search' in content_lower:
            results = self._parse_bing(content)
        elif 'class="result__a"' in content_lower or 'duckduckgo.com' in content_lower:
            results = self._parse_duckduckgo(content)
        elif 'class="snippet' in content_lower or 'search.brave.com' in content_lower:
            results = self._parse_brave(content)
        elif 'google.com/search' in content_lower:
            results = self._parse_google(content)
        else:
            # Generic fallback: extract http links with titles
            results = self._parse_generic(content)
        
        # 如果仍然没有结果，不要伪造
        return results
    
    def _parse_generic(self, html_content: str) -> List[SearchResult]:
        """通用HTML链接提取（fallback）"""
        import re
        results = []
        # 找 <a href="http...">text</a> 且 text 长度合理
        matches = re.findall(r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*>\s*([^<]{5,200}?)\s*</a>', html_content, re.IGNORECASE)
        seen_urls = set()
        for url, title in matches:
            url = url.strip()
            title = html.unescape(re.sub(r'<[^>]+>', '', title).strip())
            # 过滤明显非结果链接
            if any(bad in url.lower() for bad in ['/ads/', 'doubleclick', 'favicon', '.css', '.js', '.png', '.jpg']):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(SearchResult(
                url=url, title=title[:200], content=f"Result from: {url[:100]}",
                source="generic", quality_score=60.0, validation_score=60.0, confidence=0.50
            ))
            if len(results) >= self.max_results:
                break
        return results
    
    def process_results(self, results: List[SearchResult]) -> Dict:
        """处理多个结果"""
        if not results:
            return {"error": "无结果可验证"}
        
        # 验证每个结果
        validated_results = []
        for result in results:
            validated = self.validator.validate_single_result(result)
            validated_results.append(validated)
        
        # 统计信息
        validation_summary = {
            "total_results": len(validated_results),
            "successful_results": len([r for r in validated_results if r.validation_score >= 40]),  # 降低阈值
            "failed_results": len([r for r in validated_results if r.validation_score < 40]),
            "comparisons": []
        }
        
        # 比较结果（如果多个）
        if len(validated_results) > 1:
            comparisons = []
            for i in range(len(validated_results)):
                for j in range(i+1, len(validated_results)):
                    comparison = self.validator.compare_results(
                        validated_results[i], 
                        validated_results[j]
                    )
                    comparisons.append({
                        "result1": validated_results[i].source,
                        "result2": validated_results[j].source,
                        **comparison
                    })
            
            validation_summary["comparisons"] = comparisons
            
            # 计算一致性率
            if comparisons:
                consistent_pairs = sum(1 for c in comparisons if c["is_consistent"])
                total_pairs = len(comparisons)
                validation_summary["consistency_rate"] = consistent_pairs / total_pairs if total_pairs > 0 else 0
            else:
                validation_summary["consistency_rate"] = 0
        
        # 选择最佳结果
        sorted_results = sorted(validated_results, key=lambda x: x.validation_score, reverse=True)
        best_result = sorted_results[0] if sorted_results else None
        
        # 计算置信度
        confidence = self.calculate_confidence(best_result, validated_results, validation_summary)
        
        if best_result:
            best_result.confidence = confidence
        
        return {
            "best_result": best_result.to_dict() if best_result else None,
            "all_results": [r.to_dict() for r in validated_results],
            "validation_summary": validation_summary,
            "confidence": confidence
        }
    
    def calculate_confidence(self, best_result: SearchResult, 
                           all_results: List[SearchResult], 
                           summary: Dict) -> float:
        """计算置信度（优化版）"""
        if not best_result:
            return 0.0
        
        confidence = 0.0
        
        # 1. 最佳结果质量（40%）
        quality_factor = best_result.validation_score / 100
        confidence += quality_factor * 0.4
        
        # 2. 一致性（25%，更宽松）
        if "consistency_rate" in summary:
            consistency_factor = summary["consistency_rate"]
            # 即使一致性低，也不严重惩罚
            confidence += consistency_factor * 0.25
        else:
            # 只有一个结果，给予基础置信度
            confidence += 0.15
        
        # 3. 结果数量（20%）
        successful_count = summary.get("successful_results", 0)
        if successful_count >= 2:
            confidence += 0.2
        elif successful_count == 1:
            confidence += 0.12  # 原为0.1
        else:
            confidence += 0.05  # 即使都失败，也有基础置信度
        
        # 4. 来源可靠性（15%）
        source_scores = {
            "playwright_stealth": 0.15,
            "playwright_simple": 0.12,
            "browser_tool": 0.08,
            "web_fetch": 0.05
        }
        confidence += source_scores.get(best_result.source, 0)
        
        return min(1.0, max(0, confidence))
    
    def decide_action(self, confidence: float, best_score: float) -> str:
        """决策（优化阈值）"""
        if confidence >= 0.6:  # 原为0.8
            return "accept"
        elif confidence >= 0.4:  # 原为0.6
            return "accept_with_note"
        elif confidence >= 0.25 and best_score >= 50:  # 更宽松
            return "verify_again"
        else:
            return "reject"

def test_optimized_system():
    """测试优化后的系统"""
    print("🧪 测试优化验证系统")
    print("=" * 50)
    
    # 创建测试数据（模拟实际爬取结果）
    test_results = [
        SearchResult(
            url="https://example.com",
            title="Example Domain",
            content="Example Domain This domain is for use in documentation examples without needing permission. Avoid use in operations. Learn more",
            source="playwright_simple",
            metadata={"elapsed": 4.2}
        ),
        SearchResult(
            url="https://httpbin.org/user-agent",
            title="",
            content='{"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}',
            source="playwright_simple",
            metadata={"elapsed": 4.3}
        ),
        SearchResult(
            url="https://bad.example.com",
            title="404 Not Found",
            content="Error 404: Page not found",
            source="playwright_simple",
            metadata={"elapsed": 3.8}
        )
    ]
    
    pipeline = OptimizedValidationPipeline()
    
    print("📋 测试数据:")
    for i, result in enumerate(test_results):
        print(f"  {i+1}. {result.source}: {result.title or '无标题'}")
        print(f"     内容长度: {len(result.content)}")
        print(f"     URL: {result.url}")
    
    print("\n🔍 验证结果:")
    validation_result = pipeline.process_results(test_results)
    
    best = validation_result["best_result"]
    if best:
        print(f"🏆 最佳结果: {best['source']}")
        print(f"   验证评分: {best['validation_score']}")
        print(f"   置信度: {best['confidence']:.3f}")
        
        action = pipeline.decide_action(best['confidence'], best['validation_score'])
        print(f"   决策: {action}")
        
        if action == "accept":
            print("   ✅ 可接受结果")
        elif action == "accept_with_note":
            print("   ⚠️  可接受但需注意")
        elif action == "verify_again":
            print("   🔄 建议二次验证")
        else:
            print("   ❌ 建议拒绝")
    
    print(f"\n📊 摘要:")
    summary = validation_result["validation_summary"]
    print(f"   总结果: {summary['total_results']}")
    print(f"   成功结果: {summary['successful_results']} (评分≥40)")
    print(f"   失败结果: {summary['failed_results']}")
    
    print(f"\n📋 所有结果:")
    for i, result in enumerate(validation_result["all_results"]):
        score = result['validation_score']
        if score >= 60:
            status = "✅"
        elif score >= 40:
            status = "⚠️ "
        else:
            status = "❌"
        print(f"  {i+1}. {status} {result['source']}: {score:.1f}, 错误={result['error_count']}")

if __name__ == "__main__":
    test_optimized_system()