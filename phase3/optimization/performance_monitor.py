#!/usr/bin/env python3
"""
性能监控器
收集搜索性能指标，支持持续优化
"""

import time
import json
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics
from pathlib import Path

@dataclass
class SearchMetrics:
    """搜索指标"""
    timestamp: float
    query: str
    url: str
    engine: str
    success: bool
    total_time: float
    crawl_time: float
    validation_time: float
    cache_hit: bool
    confidence: float
    captcha_detected: bool
    captcha_solved: bool
    error: str = ""
    engine_used: str = ""
    engines_tried: int = 1
    retry_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "/tmp/smart_search_metrics.db"
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建搜索指标表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            query TEXT,
            url TEXT,
            engine TEXT,
            success INTEGER,
            total_time REAL,
            crawl_time REAL,
            validation_time REAL,
            cache_hit INTEGER,
            confidence REAL,
            captcha_detected INTEGER,
            captcha_solved INTEGER,
            error TEXT,
            engine_used TEXT,
            engines_tried INTEGER,
            retry_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建引擎性能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS engine_performance (
            engine TEXT,
            total_searches INTEGER,
            successful_searches INTEGER,
            avg_total_time REAL,
            avg_crawl_time REAL,
            avg_confidence REAL,
            captcha_rate REAL,
            last_used TIMESTAMP,
            PRIMARY KEY (engine)
        )
        ''')
        
        # 创建错误统计表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_stats (
            error_type TEXT,
            count INTEGER,
            last_occurred TIMESTAMP,
            PRIMARY KEY (error_type)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_search(self, metrics: SearchMetrics):
        """记录搜索指标"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO search_metrics 
        (timestamp, query, url, engine, success, total_time, crawl_time, validation_time, 
         cache_hit, confidence, captcha_detected, captcha_solved, error, engine_used, engines_tried, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics.timestamp,
            metrics.query[:500],  # 限制长度
            metrics.url[:500],
            metrics.engine,
            int(metrics.success),
            metrics.total_time,
            metrics.crawl_time,
            metrics.validation_time,
            int(metrics.cache_hit),
            metrics.confidence,
            int(metrics.captcha_detected),
            int(metrics.captcha_solved),
            metrics.error[:200],
            metrics.engine_used,
            metrics.engines_tried,
            metrics.retry_count
        ))
        
        # 更新引擎性能统计
        self._update_engine_stats(metrics, cursor)
        
        # 更新错误统计
        if metrics.error:
            self._update_error_stats(metrics.error, cursor)
        
        conn.commit()
        conn.close()
    
    def _update_engine_stats(self, metrics: SearchMetrics, cursor):
        """更新引擎性能统计"""
        # 获取现有统计
        cursor.execute(
            'SELECT * FROM engine_performance WHERE engine = ?',
            (metrics.engine_used or metrics.engine,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有记录
            total = existing[1] + 1
            successful = existing[2] + (1 if metrics.success else 0)
            
            # 计算新的平均值
            avg_total = (existing[3] * existing[1] + metrics.total_time) / total
            avg_crawl = (existing[4] * existing[1] + metrics.crawl_time) / total
            avg_conf = (existing[5] * existing[1] + metrics.confidence) / total
            
            # 计算验证码率
            captcha_count = existing[6] * existing[1] + (1 if metrics.captcha_detected else 0)
            captcha_rate = captcha_count / total
            
            cursor.execute('''
            UPDATE engine_performance 
            SET total_searches = ?, successful_searches = ?, 
                avg_total_time = ?, avg_crawl_time = ?, avg_confidence = ?,
                captcha_rate = ?, last_used = CURRENT_TIMESTAMP
            WHERE engine = ?
            ''', (
                total, successful, avg_total, avg_crawl, avg_conf,
                captcha_rate, metrics.engine_used or metrics.engine
            ))
        else:
            # 插入新记录
            cursor.execute('''
            INSERT INTO engine_performance 
            (engine, total_searches, successful_searches, avg_total_time, 
             avg_crawl_time, avg_confidence, captcha_rate, last_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                metrics.engine_used or metrics.engine,
                1,
                1 if metrics.success else 0,
                metrics.total_time,
                metrics.crawl_time,
                metrics.confidence,
                1.0 if metrics.captcha_detected else 0.0
            ))
    
    def _update_error_stats(self, error: str, cursor):
        """更新错误统计"""
        # 提取错误类型（第一个冒号前的部分）
        error_type = error.split(':')[0].strip() if ':' in error else error[:50]
        
        cursor.execute(
            'SELECT * FROM error_stats WHERE error_type = ?',
            (error_type,)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
            UPDATE error_stats 
            SET count = count + 1, last_occurred = CURRENT_TIMESTAMP
            WHERE error_type = ?
            ''', (error_type,))
        else:
            cursor.execute('''
            INSERT INTO error_stats (error_type, count, last_occurred)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ''', (error_type,))
    
    def get_engine_stats(self, hours: int = 24) -> Dict[str, Dict]:
        """获取引擎统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取指定时间范围内的数据
        cutoff = time.time() - (hours * 3600)
        
        cursor.execute('''
        SELECT engine_used, 
               COUNT(*) as total,
               AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate,
               AVG(total_time) as avg_time,
               AVG(confidence) as avg_confidence,
               AVG(CASE WHEN captcha_detected THEN 1 ELSE 0 END) as captcha_rate
        FROM search_metrics
        WHERE timestamp >= ?
        GROUP BY engine_used
        ORDER BY success_rate DESC, avg_time ASC
        ''', (cutoff,))
        
        results = cursor.fetchall()
        
        stats = {}
        for row in results:
            engine, total, success_rate, avg_time, avg_conf, captcha_rate = row
            stats[engine] = {
                "total_searches": total,
                "success_rate": success_rate,
                "avg_time": avg_time,
                "avg_confidence": avg_conf,
                "captcha_rate": captcha_rate
            }
        
        conn.close()
        return stats
    
    def get_recent_searches(self, limit: int = 50) -> List[Dict]:
        """获取最近的搜索记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM search_metrics 
        ORDER BY timestamp DESC 
        LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        
        conn.close()
        return results
    
    def get_error_summary(self, hours: int = 24) -> Dict:
        """获取错误摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = time.time() - (hours * 3600)
        
        cursor.execute('''
        SELECT error_type, SUM(count) as total_count
        FROM error_stats
        WHERE last_occurred >= datetime(?, 'unixepoch')
        GROUP BY error_type
        ORDER BY total_count DESC
        ''', (cutoff,))
        
        errors = cursor.fetchall()
        
        cursor.execute('''
        SELECT COUNT(*) as total_searches,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_searches
        FROM search_metrics
        WHERE timestamp >= ?
        ''', (cutoff,))
        
        totals = cursor.fetchone()
        
        conn.close()
        
        return {
            "period_hours": hours,
            "total_searches": totals[0] if totals else 0,
            "successful_searches": totals[1] if totals else 0,
            "error_types": [
                {"type": err[0], "count": err[1]}
                for err in errors
            ]
        }
    
    def calculate_engine_ranking(self, hours: int = 24) -> List[Tuple[str, float]]:
        """
        计算引擎排名（基于综合评分）
        
        评分公式:
        score = (success_rate * 0.4) + 
                ((1 - normalized_time) * 0.3) + 
                (avg_confidence * 0.2) + 
                ((1 - captcha_rate) * 0.1)
        """
        stats = self.get_engine_stats(hours)
        
        if not stats:
            return []
        
        # 计算时间归一化因子
        times = [s["avg_time"] for s in stats.values() if s["avg_time"]]
        if times:
            max_time = max(times)
            min_time = min(times)
            time_range = max_time - min_time if max_time > min_time else 1
        else:
            time_range = 1
            min_time = 0
        
        rankings = []
        for engine, stat in stats.items():
            if stat["total_searches"] < 3:  # 样本太少，可靠性低
                continue
            
            # 归一化时间（0-1，越低越好）
            if time_range > 0:
                normalized_time = (stat["avg_time"] - min_time) / time_range
            else:
                normalized_time = 0.5
            
            # 计算综合评分
            success_score = stat["success_rate"] or 0
            time_score = 1 - normalized_time
            confidence_score = stat["avg_confidence"] or 0
            captcha_score = 1 - (stat["captcha_rate"] or 0)
            
            total_score = (
                success_score * 0.4 +
                time_score * 0.3 +
                confidence_score * 0.2 +
                captcha_score * 0.1
            )
            
            rankings.append((engine, total_score))
        
        # 按评分排序
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """清理旧数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = time.time() - (days_to_keep * 86400)
        
        cursor.execute('DELETE FROM search_metrics WHERE timestamp < ?', (cutoff,))
        deleted_rows = cursor.rowcount
        
        # 重新计算引擎统计（基于剩余数据）
        cursor.execute('DELETE FROM engine_performance')
        cursor.execute('''
        INSERT INTO engine_performance 
        SELECT engine_used, 
               COUNT(*) as total_searches,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_searches,
               AVG(total_time) as avg_total_time,
               AVG(crawl_time) as avg_crawl_time,
               AVG(confidence) as avg_confidence,
               AVG(CASE WHEN captcha_detected THEN 1 ELSE 0 END) as captcha_rate,
               MAX(datetime(timestamp, 'unixepoch')) as last_used
        FROM search_metrics
        GROUP BY engine_used
        ''')
        
        conn.commit()
        conn.close()
        
        return deleted_rows

def test_performance_monitor():
    """测试性能监控器"""
    print("🧪 测试性能监控器")
    print("=" * 50)
    
    # 使用内存数据库进行测试
    monitor = PerformanceMonitor(":memory:")
    
    # 创建一些测试数据
    test_metrics = [
        SearchMetrics(
            timestamp=time.time() - 3600,
            query="test query 1",
            url="",
            engine="bing",
            success=True,
            total_time=6.5,
            crawl_time=4.2,
            validation_time=0.3,
            cache_hit=False,
            confidence=0.85,
            captcha_detected=False,
            captcha_solved=False,
            engine_used="bing",
            engines_tried=1
        ),
        SearchMetrics(
            timestamp=time.time() - 1800,
            query="test query 2",
            url="",
            engine="duckduckgo",
            success=False,
            total_time=8.2,
            crawl_time=6.7,
            validation_time=0.4,
            cache_hit=False,
            confidence=0.42,
            captcha_detected=True,
            captcha_solved=False,
            error="验证码检测",
            engine_used="duckduckgo",
            engines_tried=1
        ),
        SearchMetrics(
            timestamp=time.time() - 900,
            query="test query 3",
            url="https://example.com",
            engine="direct",
            success=True,
            total_time=4.8,
            crawl_time=4.0,
            validation_time=0.2,
            cache_hit=True,
            confidence=0.78,
            captcha_detected=False,
            captcha_solved=False,
            engine_used="direct",
            engines_tried=1
        ),
    ]
    
    # 记录测试数据
    for metrics in test_metrics:
        monitor.record_search(metrics)
    
    print("📊 引擎统计:")
    stats = monitor.get_engine_stats()
    for engine, stat in stats.items():
        print(f"  {engine}:")
        print(f"    搜索次数: {stat['total_searches']}")
        print(f"    成功率: {stat['success_rate']:.2%}")
        print(f"    平均时间: {stat['avg_time']:.1f}s")
        print(f"    平均置信度: {stat['avg_confidence']:.3f}")
        print(f"    验证码率: {stat['captcha_rate']:.2%}")
    
    print(f"\n📈 引擎排名:")
    rankings = monitor.calculate_engine_ranking()
    for engine, score in rankings:
        print(f"  {engine}: {score:.3f}")
    
    print(f"\n🔍 最近搜索:")
    recent = monitor.get_recent_searches(5)
    for i, search in enumerate(recent):
        status = "✅" if search['success'] else "❌"
        print(f"  {i+1}. {status} {search.get('query', search.get('url', 'N/A'))[:30]}")
        print(f"     引擎: {search.get('engine_used', 'N/A')}, 时间: {search['total_time']:.1f}s")
    
    print(f"\n❌ 错误摘要:")
    errors = monitor.get_error_summary()
    print(f"    总搜索: {errors['total_searches']}")
    print(f"    成功搜索: {errors['successful_searches']}")
    if errors['error_types']:
        for err in errors['error_types']:
            print(f"    错误类型: {err['type']} (次数: {err['count']})")
    
    print(f"\n{'='*50}")
    print("✅ 性能监控器测试完成")
    return True

if __name__ == "__main__":
    try:
        test_performance_monitor()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()