# Smart Search System

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Production](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![CI](https://github.com/ChenneyZhuang/smart-search-system/actions/workflows/ci.yml/badge.svg)](https://github.com/ChenneyZhuang/smart-search-system/actions/workflows/ci.yml)

> Multi-engine concurrent search + captcha detection + deep website crawling
> — evolved through 9 phases of optimization.

A high-performance web search system that concurrently queries DuckDuckGo,
Bing, Google, and Brave, with automatic captcha detection, engine fallback,
ML-based content classification, and a production-grade deep website
crawling subsystem.

---

## Table of Contents

- [Architecture](#architecture)
- [Phases of Evolution](#phases-of-evolution)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Components](#core-components)
  - [Phase 3: Concurrent Search Engine](#phase-3-concurrent-search-engine)
  - [Phase 9: Deep Website Crawling](#phase-9-deep-website-crawling)
- [Configuration](#configuration)
- [Performance](#performance)
- [FAQ](#faq)
- [License](#license)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Smart Search API                      │
│              (unified interface, async I/O)              │
└──────────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
     ┌─────▼────┐┌───▼───┐┌────▼───┐┌────▼─────┐
     │DuckDuckGo││ Bing  ││ Google ││  Brave   │
     │ (primary)││       ││        ││          │
     └─────┬────┘└───┬───┘└───┬────┘└────┬─────┘
           │         │        │          │
     ┌─────▼─────────▼────────▼──────────▼─────┐
     │         Captcha Detection Layer         │
     │   (PIL + ML classification, auto-fallback) │
     └────────────────────┬────────────────────┘
                          │
     ┌────────────────────▼────────────────────┐
     │         Result Merge + Dedup             │
     │   (score-based ranking, relevance sort)  │
     └────────────────────┬────────────────────┘
                          │
     ┌────────────────────▼────────────────────┐
     │      Deep Website Crawling (Phase 9)     │
     │  (sitemap analysis, adaptive crawling,   │
     │   anti-detection, content classification) │
     └──────────────────────────────────────────┘
```

---

## Phases of Evolution

| Phase | Focus | Key Innovation |
|-------|-------|---------------|
| **1** | Basic search | Single-engine DuckDuckGo |
| **2** | Validation | Result quality scoring, dedup |
| **3** | Concurrency | Multi-engine parallel search + captcha detection |
| **4** | Optimization | Advanced HTTP pool, similarity scoring |
| **5** | Anti-scraping | IP rotation, rate limiting, stealth strategies |
| **6** | Smart evolution | Adaptive engine selection, result caching |
| **7** | Deep integration | Unified pipeline with monitoring |
| **8** | _(merged into 9)_ | — |
| **9** | Deep crawling | Production-grade website crawler with ML classification |

---

## Installation

```bash
git clone https://github.com/ChenneyZhuang/smart-search-system.git
cd smart-search-system
pip install -r requirements.txt
playwright install chromium
```

**Requirements:** Python 3.9+, aiohttp, BeautifulSoup4, lxml, Playwright,
scikit-learn, pandas, numpy, Pillow, psutil, scipy.

---

## Quick Start

```python
from smart_search_api import SmartSearchAPI

api = SmartSearchAPI()

# Basic search
results = api.search("machine learning jobs Sydney")

# With deep crawling
results = api.search_and_crawl(
    "data science jobs",
    max_pages=10,
    max_depth=2
)

for r in results:
    print(f"{r.title} — {r.url}")
    print(f"  {r.snippet}")
```

```bash
# CLI
python3 smart_search_api.py "python developer Canberra" --engines duckduckgo,google --deep
```

---

## Core Components

### Phase 3: Concurrent Search Engine

Queries multiple search engines simultaneously with automatic fallback:
- **Playwright Simple** — fast, lightweight scraping
- **Playwright Stealth** — anti-detection with browser fingerprinting
- **HTTP Pool** — advanced connection pooling for high throughput

Engines race concurrently — the fastest valid result wins. Captcha detection
uses PIL/Pillow for image analysis and triggers automatic engine rotation.

### Phase 9: Deep Website Crawling

Production-grade website crawling subsystem:
- **Sitemap Analyzer** — discovers all pages via XML sitemaps
- **Adaptive Crawler** — adjusts crawl depth based on page relevance
- **Anti-Anti-Crawler** — IP rotation, user-agent cycling, rate limiting
- **ML Content Classifier** — scikit-learn based job/content relevance scoring
- **Link Discovery Engine** — extracts and prioritizes internal links
- **Performance Optimizer** — memory management, connection pooling, throttling
- **Monitoring System** — real-time crawl metrics and health checks

---

## Configuration

Configuration is split across three JSON files for clarity:

| File | Purpose |
|------|---------|
| `deep_crawl_defaults.json` | Global defaults (timeouts, concurrency, user agent) |
| `website_strategies.json` | Per-site crawling strategies |
| `job_websites.json` | Target job boards and their selectors |

Settings cascade: `job_websites.json` > `website_strategies.json` > `deep_crawl_defaults.json`.

---

## Performance

Benchmarks on a 2024 Mac mini (16 GB RAM, 8-core):

| Scenario | Engines | Results | Time |
|----------|---------|---------|------|
| Simple search | 1 (DDG) | 10 | ~0.8s |
| Multi-engine | 4 concurrent | 40 | ~2.1s |
| Deep crawl | 1 site, depth 2 | ~50 pages | ~12s |
| Full pipeline | 4 engines + crawl 3 sites | ~200 pages | ~35s |

---

## FAQ

**Why not use an API-based search service?**
API services cost money per query. This system runs entirely locally with
zero per-query cost.

**Is this legal for job scraping?**
Check each website's robots.txt and terms of service. This system respects
robots.txt by default and includes rate limiting.

**Can I use this for non-job searches?**
Yes. The architecture is generic — swap the target URLs and selectors for
any domain.

---

## License

MIT
