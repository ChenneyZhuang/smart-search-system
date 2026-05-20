# Smart Search System

> Multi-engine concurrent search + captcha detection + deep website crawling

A multi-engine web search system that concurrently searches DuckDuckGo / Bing / Google / Brave, with automatic captcha detection, engine fallback, and a production-grade deep website crawling subsystem.

## Features

- **Multi-engine concurrent** — aiohttp + Playwright strategy auto-switching  
- **Deep crawling** — full-site crawl, link discovery, sitemap analysis  
- **Anti-bot countermeasures** — fingerprint rotation, behavior simulation, IP proxies  
- **Smart classification** — ML content classifier, URL type recognition  
- **Caching** — TTL-based memory cache with hot-key prediction  

## Architecture

```
smart_search_api.py (entry point)
  ├── ConcurrentCrawler (aiohttp + Playwright)
  ├── ValidationPipeline (text similarity + confidence)
  ├── MemoryCache (TTL + hot-key prediction)
  └── PerformanceMonitor

phase9_deep_crawl/ (deep crawl subsystem)
  ├── website_deep_crawler.py    — core crawler
  ├── link_discovery_engine.py   — link extraction
  ├── sitemap_analyzer.py        — sitemap parsing
  ├── content_classifier.py      — page type detection
  ├── ml_content_classifier.py   — ML-based classification
  ├── adaptive_crawler.py        — dynamic strategy adjustment
  ├── anti_anti_crawler.py       — fingerprint rotation
  ├── performance_optimizer.py   — connection pool, caching
  ├── monitoring_system.py       — real-time metrics
  └── integration_adapter.py     — job_monitor_project bridge
```

## Performance

| Metric | Before | After |
|--------|--------|-------|
| Search success rate | 46.2% | **100%** |
| Avg search time | 12.5s | **5.63s** |
| HTML parse speed | ~5ms | **0.27ms** (18×) |

## Quick Start

```bash
pip install -r requirements.txt
playwright install
```

```python
from smart_search_api import SmartSearchAPI

api = SmartSearchAPI()
results = api.search("Canberra data analyst jobs", limit=10)
```

### Deep Crawl

```python
from phase9_deep_crawl import WebsiteDeepCrawler, DeepCrawlConfig

config = DeepCrawlConfig(max_depth=3, max_pages=100)
crawler = WebsiteDeepCrawler(config)
results = await crawler.deep_crawl("https://au.indeed.com/jobs?q=data+analyst")
```

## Version History

| Phase | Capability |
|-------|-----------|
| Phase 2 | Text validation, conflict resolution |
| Phase 3 | Concurrent crawling, Playwright, caching |
| Phase 4 | URL classification, advanced similarity |
| Phase 5 | Performance breakthrough |
| Phase 6 | ML prediction, adaptive optimization |
| Phase 7 | A/B testing framework |
| Phase 9 | Deep website crawling (current main) |

*Archived phases in `.archive/`*

## License

MIT — Chenney Zhuang
