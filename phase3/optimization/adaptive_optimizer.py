#!/usr/bin/env python3
"""
自适应优化器
基于性能数据自动优化搜索系统
"""

import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import statistics
from datetime import datetime, timedelta

try:
    from .performance_monitor import PerformanceMonitor
except ImportError:
    # 回退到绝对导入
    from phase3.optimization.performance_monitor import PerformanceMonitor

@dataclass
class OptimizationSuggestion:
    """优化建议"""
    type: str  # engine_priority, timeout, retry_strategy, etc.
    description: str
    current_value: Any
    suggested_value: Any
    confidence: float  # 建议置信度 (0-1)
    expected_improvement: float  # 预期改进百分比
    priority: int = 1  # 优先级 (1-5, 1最高)
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass  
class OptimizationReport:
    """优化报告"""
    timestamp: float
    suggestions: List[OptimizationSuggestion]
    performance_summary: Dict
    applied_changes: List[str] = None
    
    def __post_init__(self):
        if self.applied_changes is None:
            self.applied_changes = []

class AdaptiveOptimizer:
    """自适应优化器"""
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
        self.min_samples_per_engine = 5  # 每个引擎最小样本数
    
    def analyze_performance(self, hours: int = 24) -> Dict:
        """分析性能数据，返回诊断结果"""
        print(f"📊 分析过去 {hours} 小时性能数据...")
        
        # 获取引擎统计
        engine_stats = self.monitor.get_engine_stats(hours)
        
        # 获取错误摘要
        error_summary = self.monitor.get_error_summary(hours)
        
        # 获取引擎排名
        rankings = self.monitor.calculate_engine_ranking(hours)
        
        # 计算整体性能指标
        overall_stats = self._calculate_overall_stats(engine_stats, error_summary)
        
        # 识别问题
        problems = self._identify_problems(engine_stats, error_summary)
        
        return {
            "analysis_period_hours": hours,
            "overall_performance": overall_stats,
            "engine_rankings": [
                {"engine": engine, "score": score}
                for engine, score in rankings
            ],
            "engine_statistics": engine_stats,
            "error_summary": error_summary,
            "identified_problems": problems,
            "total_samples": sum(stat["total_searches"] for stat in engine_stats.values())
        }
    
    def generate_suggestions(self, hours: int = 24) -> List[OptimizationSuggestion]:
        """生成优化建议"""
        print(f"💡 生成优化建议...")
        
        suggestions = []
        
        # 分析性能数据
        analysis = self.analyze_performance(hours)
        
        # 1. 引擎优先级建议
        engine_suggestions = self._suggest_engine_optimizations(analysis)
        suggestions.extend(engine_suggestions)
        
        # 2. 超时参数建议
        timeout_suggestions = self._suggest_timeout_optimizations(analysis)
        suggestions.extend(timeout_suggestions)
        
        # 3. 重试策略建议
        retry_suggestions = self._suggest_retry_optimizations(analysis)
        suggestions.extend(retry_suggestions)
        
        # 4. 验证码处理建议
        captcha_suggestions = self._suggest_captcha_optimizations(analysis)
        suggestions.extend(captcha_suggestions)
        
        # 5. 缓存策略建议
        cache_suggestions = self._suggest_cache_optimizations(analysis)
        suggestions.extend(cache_suggestions)
        
        # 按优先级排序
        suggestions.sort(key=lambda x: (x.priority, -x.confidence))
        
        return suggestions
    
    def _calculate_overall_stats(self, engine_stats: Dict, error_summary: Dict) -> Dict:
        """计算整体性能统计"""
        if not engine_stats:
            return {}
        
        total_searches = error_summary.get("total_searches", 0)
        successful_searches = error_summary.get("successful_searches", 0)
        
        overall_success_rate = successful_searches / total_searches if total_searches > 0 else 0
        
        # 计算平均时间
        avg_times = []
        avg_confidences = []
        captcha_rates = []
        
        for stat in engine_stats.values():
            if stat["total_searches"] > 0:
                avg_times.append(stat["avg_time"])
                avg_confidences.append(stat["avg_confidence"])
                captcha_rates.append(stat["captcha_rate"])
        
        avg_time = statistics.mean(avg_times) if avg_times else 0
        avg_confidence = statistics.mean(avg_confidences) if avg_confidences else 0
        avg_captcha_rate = statistics.mean(captcha_rates) if captcha_rates else 0
        
        return {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "success_rate": overall_success_rate,
            "average_time": avg_time,
            "average_confidence": avg_confidence,
            "average_captcha_rate": avg_captcha_rate
        }
    
    def _identify_problems(self, engine_stats: Dict, error_summary: Dict) -> List[Dict]:
        """识别问题"""
        problems = []
        
        # 检查引擎成功率
        for engine, stat in engine_stats.items():
            if stat["total_searches"] >= self.min_samples_per_engine:
                if stat["success_rate"] < 0.5:  # 成功率低于50%
                    problems.append({
                        "type": "low_success_rate",
                        "engine": engine,
                        "severity": "high" if stat["success_rate"] < 0.3 else "medium",
                        "current_rate": stat["success_rate"],
                        "description": f"引擎 {engine} 成功率过低 ({stat['success_rate']:.1%})"
                    })
                
                if stat["avg_time"] > 15:  # 平均时间超过15秒
                    problems.append({
                        "type": "high_latency",
                        "engine": engine,
                        "severity": "medium",
                        "current_time": stat["avg_time"],
                        "description": f"引擎 {engine} 响应时间过长 ({stat['avg_time']:.1f}s)"
                    })
                
                if stat["captcha_rate"] > 0.5:  # 验证码率超过50%
                    problems.append({
                        "type": "high_captcha_rate",
                        "engine": engine,
                        "severity": "medium",
                        "current_rate": stat["captcha_rate"],
                        "description": f"引擎 {engine} 验证码率过高 ({stat['captcha_rate']:.1%})"
                    })
        
        # 检查错误模式
        for error in error_summary.get("error_types", []):
            if error["count"] >= 5:  # 同一错误出现5次以上
                problems.append({
                    "type": "common_error",
                    "error_type": error["type"],
                    "count": error["count"],
                    "severity": "medium",
                    "description": f"常见错误: {error['type']} (出现 {error['count']} 次)"
                })
        
        return problems
    
    def _suggest_engine_optimizations(self, analysis: Dict) -> List[OptimizationSuggestion]:
        """生成引擎优化建议"""
        suggestions = []
        
        rankings = analysis.get("engine_rankings", [])
        if len(rankings) < 2:
            return suggestions
        
        # 检查当前排名是否合理
        current_top = rankings[0] if rankings else None
        current_bottom = rankings[-1] if rankings else None
        
        if current_top and current_bottom:
            # 如果排名第一和最后的引擎得分差异很大
            score_diff = current_top["score"] - current_bottom["score"]
            if score_diff > 0.3:  # 差异大于0.3
                suggestions.append(OptimizationSuggestion(
                    type="engine_priority",
                    description=f"引擎性能差异显著，建议优先使用 {current_top['engine']}",
                    current_value="所有引擎平等使用",
                    suggested_value=f"优先使用 {current_top['engine']}",
                    confidence=0.8,
                    expected_improvement=0.15,
                    priority=1
                ))
        
        # 检查是否有引擎表现特别差
        for engine_rank in rankings:
            engine = engine_rank["engine"]
            score = engine_rank["score"]
            
            if score < 0.4:  # 得分低于0.4
                stats = analysis["engine_statistics"].get(engine, {})
                if stats.get("total_searches", 0) >= self.min_samples_per_engine:
                    suggestions.append(OptimizationSuggestion(
                        type="engine_exclusion",
                        description=f"引擎 {engine} 性能较差，考虑排除或降低优先级",
                        current_value=f"包含 {engine}",
                        suggested_value=f"排除 {engine} 或作为最后备用",
                        confidence=0.7,
                        expected_improvement=0.1,
                        priority=2
                    ))
        
        return suggestions
    
    def _suggest_timeout_optimizations(self, analysis: Dict) -> List[OptimizationSuggestion]:
        """生成超时参数建议"""
        suggestions = []
        
        engine_stats = analysis.get("engine_statistics", {})
        overall_stats = analysis.get("overall_performance", {})
        
        # 检查平均响应时间
        avg_time = overall_stats.get("average_time", 0)
        
        if avg_time > 0:
            # 如果平均时间较长，建议增加超时
            if avg_time > 12:  # 平均超过12秒
                suggested_timeout = min(60, int(avg_time * 2))  # 建议2倍平均时间，最多60秒
                suggestions.append(OptimizationSuggestion(
                    type="timeout_adjustment",
                    description=f"系统平均响应时间较长 ({avg_time:.1f}s)，建议增加超时设置",
                    current_value="30秒",
                    suggested_value=f"{suggested_timeout}秒",
                    confidence=0.7,
                    expected_improvement=0.1,
                    priority=2
                ))
            
            # 如果平均时间很短，建议减少超时
            elif avg_time < 5:  # 平均低于5秒
                suggested_timeout = max(15, int(avg_time * 3))  # 建议3倍平均时间，最少15秒
                suggestions.append(OptimizationSuggestion(
                    type="timeout_adjustment",
                    description=f"系统平均响应时间较短 ({avg_time:.1f}s)，建议减少超时设置以提高响应速度",
                    current_value="30秒",
                    suggested_value=f"{suggested_timeout}秒",
                    confidence=0.6,
                    expected_improvement=0.05,
                    priority=3
                ))
        
        return suggestions
    
    def _suggest_retry_optimizations(self, analysis: Dict) -> List[OptimizationSuggestion]:
        """生成重试策略建议"""
        suggestions = []
        
        overall_stats = analysis.get("overall_performance", {})
        success_rate = overall_stats.get("success_rate", 0)
        
        if success_rate > 0:
            # 如果成功率较低，建议增加重试次数
            if success_rate < 0.7:  # 成功率低于70%
                suggestions.append(OptimizationSuggestion(
                    type="retry_strategy",
                    description=f"系统成功率较低 ({success_rate:.1%})，建议增加重试次数",
                    current_value="不重试或重试1次",
                    suggested_value="重试2-3次",
                    confidence=0.7,
                    expected_improvement=0.15,
                    priority=2
                ))
            
            # 如果成功率很高，可以减少重试
            elif success_rate > 0.9:  # 成功率高于90%
                suggestions.append(OptimizationSuggestion(
                    type="retry_strategy",
                    description=f"系统成功率很高 ({success_rate:.1%})，可以减少重试以提升性能",
                    current_value="重试2-3次",
                    suggested_value="重试1次或不重试",
                    confidence=0.6,
                    expected_improvement=0.05,
                    priority=3
                ))
        
        return suggestions
    
    def _suggest_captcha_optimizations(self, analysis: Dict) -> List[OptimizationSuggestion]:
        """生成验证码处理建议"""
        suggestions = []
        
        overall_stats = analysis.get("overall_performance", {})
        captcha_rate = overall_stats.get("average_captcha_rate", 0)
        
        if captcha_rate > 0.3:  # 验证码率超过30%
            suggestions.append(OptimizationSuggestion(
                type="captcha_handling",
                description=f"系统验证码率较高 ({captcha_rate:.1%})，建议优化验证码处理策略",
                current_value="检测到验证码即切换引擎",
                suggested_value="尝试自动解决验证码",
                confidence=0.8,
                expected_improvement=0.2,
                priority=1
            ))
        
        # 检查特定引擎的验证码率
        engine_stats = analysis.get("engine_statistics", {})
        for engine, stats in engine_stats.items():
            if stats.get("captcha_rate", 0) > 0.6:  # 验证码率超过60%
                suggestions.append(OptimizationSuggestion(
                    type="engine_captcha",
                    description=f"引擎 {engine} 验证码率极高 ({stats['captcha_rate']:.1%})",
                    current_value=f"继续使用 {engine}",
                    suggested_value=f"将 {engine} 设为最后备用或排除",
                    confidence=0.9,
                    expected_improvement=0.15,
                    priority=1
                ))
        
        return suggestions
    
    def _suggest_cache_optimizations(self, analysis: Dict) -> List[OptimizationSuggestion]:
        """生成缓存策略建议"""
        suggestions = []
        
        # 获取最近搜索数据
        recent_searches = self.monitor.get_recent_searches(100)
        
        if not recent_searches:
            return suggestions
        
        # 分析重复查询
        query_counts = {}
        for search in recent_searches:
            query = search.get("query") or search.get("url")
            if query:
                query_counts[query] = query_counts.get(query, 0) + 1
        
        # 计算重复率
        total_searches = len(recent_searches)
        unique_queries = len(query_counts)
        duplicate_rate = 1 - (unique_queries / total_searches) if total_searches > 0 else 0
        
        if duplicate_rate > 0.3:  # 重复率超过30%
            # 检查缓存命中率
            cache_hits = sum(1 for s in recent_searches if s.get("cache_hit"))
            cache_hit_rate = cache_hits / total_searches if total_searches > 0 else 0
            
            if cache_hit_rate < 0.5:  # 缓存命中率低于50%
                suggestions.append(OptimizationSuggestion(
                    type="cache_strategy",
                    description=f"查询重复率较高 ({duplicate_rate:.1%}) 但缓存命中率较低 ({cache_hit_rate:.1%})",
                    current_value="当前缓存策略",
                    suggested_value="增加缓存TTL或优化缓存键",
                    confidence=0.7,
                    expected_improvement=0.2,
                    priority=2
                ))
        
        return suggestions
    
    def create_optimization_report(self, hours: int = 24) -> OptimizationReport:
        """创建完整的优化报告"""
        suggestions = self.generate_suggestions(hours)
        
        # 获取性能摘要
        analysis = self.analyze_performance(hours)
        
        report = OptimizationReport(
            timestamp=time.time(),
            suggestions=suggestions,
            performance_summary=analysis.get("overall_performance", {})
        )
        
        return report
    
    def apply_optimization(self, suggestion: OptimizationSuggestion) -> Dict:
        """
        应用优化建议
        
        Note: 在实际系统中，这会更新配置文件或系统参数
        这里只是模拟应用过程
        """
        print(f"🔧 应用优化: {suggestion.description}")
        
        # 模拟应用优化
        change_summary = {
            "suggestion_type": suggestion.type,
            "description": suggestion.description,
            "applied_at": time.time(),
            "success": True  # 假设总是成功
        }
        
        # 根据建议类型记录具体操作
        if suggestion.type == "engine_priority":
            change_summary["action"] = f"更新引擎优先级: {suggestion.suggested_value}"
        elif suggestion.type == "timeout_adjustment":
            change_summary["action"] = f"更新超时设置: {suggestion.suggested_value}"
        elif suggestion.type == "retry_strategy":
            change_summary["action"] = f"更新重试策略: {suggestion.suggested_value}"
        elif suggestion.type.startswith("captcha"):
            change_summary["action"] = f"更新验证码处理: {suggestion.suggested_value}"
        elif suggestion.type.startswith("cache"):
            change_summary["action"] = f"更新缓存策略: {suggestion.suggested_value}"
        else:
            change_summary["action"] = "应用未知类型优化"
        
        return change_summary

def test_adaptive_optimizer():
    """测试自适应优化器"""
    print("🧪 测试自适应优化器")
    print("=" * 50)
    
    # 创建监控器（使用内存数据库）
    monitor = PerformanceMonitor(":memory:")
    
    # 创建一些测试数据
    test_time = time.time()
    
    # 模拟不同引擎的性能数据
    engines = ["bing", "duckduckgo", "google", "brave"]
    performance_data = {
        "bing": {"success_rate": 0.95, "avg_time": 6.5, "captcha_rate": 0.05},
        "duckduckgo": {"success_rate": 0.45, "avg_time": 8.2, "captcha_rate": 0.65},
        "google": {"success_rate": 0.35, "avg_time": 12.8, "captcha_rate": 0.85},
        "brave": {"success_rate": 0.75, "avg_time": 7.1, "captcha_rate": 0.25},
    }
    
    # 生成测试数据
    for engine, stats in performance_data.items():
        for i in range(10):  # 每个引擎10个样本
            try:
                from .performance_monitor import SearchMetrics
            except ImportError:
                from phase3.optimization.performance_monitor import SearchMetrics
            
            metrics = SearchMetrics(
                timestamp=test_time - i * 3600,  # 分布在过去时间
                query=f"test query {i}",
                url="",
                engine=engine,
                success=(i < int(stats["success_rate"] * 10)),  # 按成功率设置成功/失败
                total_time=stats["avg_time"] + (i % 3),  # 添加一些变化
                crawl_time=stats["avg_time"] * 0.8,
                validation_time=0.3,
                cache_hit=(i % 5 == 0),  # 20%缓存命中
                confidence=0.8 if i < int(stats["success_rate"] * 10) else 0.3,
                captcha_detected=(i < int(stats["captcha_rate"] * 10)),
                captcha_solved=(i < int(stats["captcha_rate"] * 10 * 0.3)),  # 30%解决率
                engine_used=engine,
                engines_tried=1
            )
            
            if not metrics.success:
                metrics.error = "验证码检测" if metrics.captcha_detected else "超时"
            
            monitor.record_search(metrics)
    
    # 创建优化器
    optimizer = AdaptiveOptimizer(monitor)
    
    print("📊 性能分析结果:")
    analysis = optimizer.analyze_performance(hours=24)
    
    print(f"  总搜索次数: {analysis['overall_performance'].get('total_searches', 0)}")
    print(f"  整体成功率: {analysis['overall_performance'].get('success_rate', 0):.1%}")
    print(f"  平均响应时间: {analysis['overall_performance'].get('average_time', 0):.1f}s")
    print(f"  平均验证码率: {analysis['overall_performance'].get('average_captcha_rate', 0):.1%}")
    
    print(f"\n🏆 引擎排名:")
    for rank in analysis.get("engine_rankings", []):
        print(f"  {rank['engine']}: {rank['score']:.3f}")
    
    print(f"\n⚠️  识别到的问题:")
    for problem in analysis.get("identified_problems", []):
        print(f"  {problem['description']}")
    
    print(f"\n💡 优化建议:")
    suggestions = optimizer.generate_suggestions(hours=24)
    
    for i, suggestion in enumerate(suggestions[:5]):  # 显示前5个建议
        print(f"  {i+1}. [{suggestion.type}] {suggestion.description}")
        print(f"     当前: {suggestion.current_value}")
        print(f"     建议: {suggestion.suggested_value}")
        print(f"     置信度: {suggestion.confidence:.1f}, 预期改进: {suggestion.expected_improvement:.1%}")
        print(f"     优先级: {suggestion.priority}")
    
    print(f"\n📋 创建完整报告...")
    report = optimizer.create_optimization_report(hours=24)
    print(f"  报告时间: {datetime.fromtimestamp(report.timestamp)}")
    print(f"  建议总数: {len(report.suggestions)}")
    
    print(f"\n{'='*50}")
    print("✅ 自适应优化器测试完成")
    return True

if __name__ == "__main__":
    try:
        test_adaptive_optimizer()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()