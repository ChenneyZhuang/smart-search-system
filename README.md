# 🔍 Smart Search System

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Production](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![CI](https://github.com/ChenneyZhuang/smart-search-system/actions/workflows/ci.yml/badge.svg)](https://github.com/ChenneyZhuang/smart-search-system/actions/workflows/ci.yml)

> Multi-engine concurrent search + captcha detection + deep website crawling — evolved through 9 phases of optimization.

A high-performance web search system that concurrently queries DuckDuckGo / Bing / Google / Brave, with automatic captcha detection, engine fallback, ML-based content classification, and a production-grade deep website crawling subsystem.

---

## 📑 Table of Contents

- [Performance](#-performance)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Features](#-features)
- [Deep Crawl Subsystem](#-deep-crawl-subsystem)
- [Version History](#-version-history)
- [License](#-license)

---

## ⚡ Performance

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Search success rate | 46.2% | **100%** | 2.2× |
| Avg search time | 12.5s | **5.63s** | 2.2× |
| HTML parse speed | ~5ms | **0.27ms** | **18×** |

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
playwright install
```

### Basic Search

```python
from smart_search_api import SmartSearchAPI

api = SmartSearchAPI()
results = api.search("Canberra data analyst jobs", limit=10)

for r in results:
    print(f"{r['title']}\n  {r['url']}\n")
```

### Deep Website Crawl

```python
from phase9_deep_crawl import WebsiteDeepCrawler, DeepCrawlConfig

config = DeepCrawlConfig(
    max_depth=3,
    max_pages=100,
    respect_robots=True,
    enable_sitemap=True
)

crawler = WebsiteDeepCrawler(config)
results = await crawler.deep_crawl("https://au.indeed.com/jobs?q=data+analyst")

print(f"Crawled {len(results['pages'])} pages, found {len(results['jobs'])} jobs")
```

---

## 🏗 Architecture

```
smart_search_api.py (entry point)
  ├── ConcurrentCrawler (aiohttp + Playwright auto-switching)
  ├── ValidationPipeline (text similarity + confidence scoring)
  ├── MemoryCache (TTL + hot-key prediction)
  └── PerformanceMonitor (real-time metrics)

phase9_deep_crawl/ (deep crawl subsystem)
  ├── website_deep_crawler.py    — core crawler engine
  ├── link_discovery_engine.py   — intelligent link extraction
  ├── sitemap_analyzer.py        — sitemap.xml parsing
  ├── content_classifier.py      — page type detection
  ├── ml_content_classifier.py   — ML-based job/content classification
  ├── adaptive_crawler.py        — dynamic strategy adjustment
  ├── anti_anti_crawler.py       — fingerprint rotation, IP proxies
  ├── performance_optimizer.py   — connection pooling, caching
  ├── monitoring_system.py       — real-time alerts, logging
  └── integration_adapter.py     — bridge to job_monitor_project
```

**Data flow:**
```
User Query → Engine Selection → Concurrent Fetch → Validation → Cache → Results
                                                    ↓
                                            Captcha? → Fallback Engine
```

---

## ✨ Features

### Search
- **4 search engines** — DuckDuckGo, Bing, Google, Brave — queried concurrently
- **Smart fallback** — captcha detected? auto-switch to next engine
- **aiohttp + Playwright** — fast HTTP where possible, full browser where needed

### Deep Crawl
- **Full-site traversal** — configurable depth (1–10) and page limits (10–1000)
- **Link discovery** — sitemap analysis, pagination detection, priority queue
- **Content classification** — ML-based job page detection, relevance scoring
- **Deduplication** — URL + content-based dedup, similarity threshold

### Anti-Detection
- **Fingerprint rotation** — 7 User-Agents, randomized headers, canvas/WebGL spoofing
- **Behavior simulation** — human-like delays (1–5s random), natural click patterns
- **Proxy support** — optional IP rotation pool

### Performance
- **Memory cache** — TTL-based with hot-key prediction
- **Connection pooling** — persistent HTTP connections
- **Parallel execution** — asyncio-based concurrent crawling

---

## 🕸 Deep Crawl Subsystem

The crown jewel — `phase9_deep_crawl/` contains 12 modules:

| Module | Purpose |
|--------|---------|
| `website_deep_crawler.py` | Core crawler — BFS traversal, depth/breadth control |
| `link_discovery_engine.py` | URL extraction, pagination patterns, priority scoring |
| `sitemap_analyzer.py` | Auto-discovers and parses `sitemap.xml` |
| `content_classifier.py` | HTML structure analysis, page type detection |
| `ml_content_classifier.py` | NLP-based job description classifier |
| `adaptive_crawler.py` | Adjusts speed/strategy based on site responsiveness |
| `anti_anti_crawler.py` | Fingerprint rotation, request header randomization |
| `performance_optimizer.py` | Connection pool, in-memory cache, resource limits |
| `monitoring_system.py` | Real-time metrics dashboard, alert thresholds |
| `integration_adapter.py` | Seamless bridge to job_monitor_project |
| `simple_adapter.py` | Lightweight wrapper for quick integration |
| `fallback/` | Graceful degradation when optional deps unavailable |

---

## 📜 Version History

| Phase | Capability | Status |
|-------|-----------|--------|
| Phase 1 | Basic multi-engine search | Archived |
| Phase 2 | Text validation, conflict resolution | Active |
| Phase 3 | Concurrent crawling, Playwright, caching | Active |
| Phase 4 | URL classification, advanced similarity | Archived |
| Phase 5 | Performance breakthrough | Archived |
| Phase 6 | ML prediction, adaptive optimization | Archived |
| Phase 7 | A/B testing framework | Archived |
| Phase 9 | **Deep website crawling** | **Active** |

---

## 📄 License

MIT — [Chenney Zhuang](https://github.com/ChenneyZhuang)
