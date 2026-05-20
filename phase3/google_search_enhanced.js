#!/usr/bin/env node
/**
 * Google搜索增强爬取器
 * 专门针对Google反爬设计
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const url = process.argv[2];
const query = process.argv[3] || '';

if (!url && !query) {
    console.error('❌ 请提供URL或搜索词');
    console.error('用法: node google_search_enhanced.js <URL> [搜索词]');
    process.exit(1);
}

// 最终URL
const targetUrl = url || `https://www.google.com/search?q=${encodeURIComponent(query)}`;

(async () => {
    console.log('🔍 Google搜索增强爬取器启动...');
    console.log(`🎯 目标: ${targetUrl}`);
    
    const startTime = Date.now();
    
    // 使用headless模式（可通过环境变量控制）
    const forceHeadless = process.env.FORCE_HEADLESS === 'true';
    const headlessMode = forceHeadless ? true : false;  // 默认非headless
    
    const browser = await chromium.launch({
        headless: headlessMode,  // 可通过环境变量控制
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--no-first-run',
            '--no-zygote',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
        ],
        // 使用真实的Chrome安装路径
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    });
    
    // 创建复杂的上下文，模拟真实用户
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        locale: 'en-US,en;q=0.9',
        timezoneId: 'America/New_York',
        permissions: ['geolocation', 'notifications'],
        viewport: { width: 1920, height: 1080 },
        colorScheme: 'light',
        deviceScaleFactor: 1,
        hasTouch: false,
        isMobile: false,
        extraHTTPHeaders: {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        },
        // 设置cookies（可选）
        // storageState: { cookies: [...] }
    });
    
    // 添加复杂的指纹隐藏
    await context.addInitScript(() => {
        // 隐藏自动化特征
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });
        
        // 修改chrome属性
        window.chrome = {
            app: {
                isInstalled: false,
                InstallState: { DISABLED: 'disabled' },
                RunningState: { STOPPED: 'stopped' },
            },
            runtime: {
                OnInstalledReason: { INSTALL: 'install' },
                OnRestartRequiredReason: { APP_UPDATE: 'app_update' },
                PlatformOs: { MAC: 'mac' },
                PlatformArch: { X86_64: 'x86-64' },
                PlatformNaclArch: { X86_64: 'x86-64' },
                RequestUpdateCheckStatus: { THROTTLED: 'throttled' },
            },
        };
        
        // 修改插件
        const originalPlugins = Object.getOwnPropertyDescriptor(Navigator.prototype, 'plugins');
        Object.defineProperty(navigator, 'plugins', {
            ...originalPlugins,
            get: function() {
                const plugins = originalPlugins.get.call(this);
                return {
                    ...plugins,
                    length: 5,
                    [0]: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    [1]: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    [2]: { name: 'Native Client', filename: 'internal-nacl-plugin' },
                };
            },
        });
        
        // 修改语言
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // 修改硬件并发
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
        });
        
        // 修改屏幕属性
        Object.defineProperty(screen, 'width', { get: () => 1920 });
        Object.defineProperty(screen, 'height', { get: () => 1080 });
        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
        Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
        
        // 修改平台
        Object.defineProperty(navigator, 'platform', {
            get: () => 'MacIntel',
        });
        
        // 修改vendor
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.',
        });
        
        // 模拟用户活动
        let lastMouseMove = 0;
        document.addEventListener('mousemove', (e) => {
            lastMouseMove = Date.now();
        });
        
        // 添加滚动监听
        let lastScroll = 0;
        window.addEventListener('scroll', () => {
            lastScroll = Date.now();
        });
        
        // 暴露这些时间给脚本
        window._lastUserActivity = {
            mouseMove: lastMouseMove,
            scroll: lastScroll,
        };
    });
    
    const page = await context.newPage();
    
    console.log('🧭 导航到页面...');
    
    try {
        // 添加随机延迟（模拟用户思考）
        const randomDelay = Math.random() * 2000 + 1000;
        console.log(`⏳ 随机延迟: ${Math.round(randomDelay)}ms`);
        await page.waitForTimeout(randomDelay);
        
        // 导航
        const response = await page.goto(targetUrl, {
            waitUntil: 'networkidle',  // 等待网络空闲
            timeout: 45000,
        });
        
        console.log(`📡 HTTP状态: ${response.status()}`);
        
        // 如果遇到反爬页面，尝试解决
        const pageContent = await page.content();
        if (pageContent.includes('異常情況') || pageContent.includes('automated')) {
            console.log('⚠️  检测到反爬页面，尝试绕过...');
            
            // 等待更长时间
            await page.waitForTimeout(10000);
            
            // 模拟人类行为
            await humanLikeBehavior(page);
            
            // 尝试重新加载
            await page.reload({ waitUntil: 'networkidle' });
        }
        
        // 模拟人类浏览行为
        await humanLikeBehavior(page);
        
        // 提取搜索结果
        console.log('🔍 提取搜索结果...');
        const searchResults = await extractGoogleResults(page);
        
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        
        const result = {
            success: true,
            url: targetUrl,
            query: query,
            title: await page.title(),
            elapsedSeconds: elapsed,
            searchResults: searchResults,
            pageInfo: {
                contentLength: pageContent.length,
                hasSearchResults: searchResults.length > 0,
                detectedAntiBot: pageContent.includes('異常情況') || pageContent.includes('automated')
            }
        };
        
        console.log('\n✅ 爬取完成！');
        console.log(JSON.stringify(result, null, 2));
        
        // 保持浏览器打开一段时间（可选）
        await page.waitForTimeout(3000);
        
        await browser.close();
        
    } catch (error) {
        console.error(`❌ 爬取失败: ${error.message}`);
        
        const errorResult = {
            success: false,
            url: targetUrl,
            error: error.message,
            elapsedSeconds: ((Date.now() - startTime) / 1000).toFixed(2)
        };
        
        console.log(JSON.stringify(errorResult, null, 2));
        
        try {
            await browser.close();
        } catch (e) {
            // 忽略关闭错误
        }
        
        process.exit(1);
    }
})();

/**
 * 模拟人类行为
 */
async function humanLikeBehavior(page) {
    console.log('👤 模拟人类行为...');
    
    // 随机滚动
    const scrollTimes = Math.floor(Math.random() * 5) + 3;
    for (let i = 0; i < scrollTimes; i++) {
        const scrollAmount = Math.random() * 800 + 200;
        await page.mouse.wheel(0, scrollAmount);
        await page.waitForTimeout(Math.random() * 1000 + 500);
    }
    
    // 随机鼠标移动
    const moveTimes = Math.floor(Math.random() * 10) + 5;
    const viewport = page.viewportSize();
    
    for (let i = 0; i < moveTimes; i++) {
        const x = Math.random() * viewport.width;
        const y = Math.random() * viewport.height;
        await page.mouse.move(x, y);
        await page.waitForTimeout(Math.random() * 300 + 200);
    }
    
    // 随机点击（如果有可点击元素）
    try {
        const clickableElements = await page.$$('a, button, [role="button"]');
        if (clickableElements.length > 0) {
            const randomElement = clickableElements[Math.floor(Math.random() * clickableElements.length)];
            await randomElement.click();
            await page.waitForTimeout(Math.random() * 2000 + 1000);
            // 可能后退
            if (Math.random() > 0.7) {
                await page.goBack();
                await page.waitForTimeout(1000);
            }
        }
    } catch (error) {
        // 点击失败也没关系
    }
}

/**
 * 提取Google搜索结果
 */
async function extractGoogleResults(page) {
    try {
        return await page.evaluate(() => {
            const results = [];
            
            // 尝试多种选择器（Google经常变化）
            const selectors = [
                'div.g',  // 传统结果
                'div[data-sokoban-container]',  // 新布局
                'div[jscontroller="SC7lYd"]',  // 另一种
                'div.yuRUbf',  // 搜索结果
                'div.tF2Cxc'   // 另一种
            ];
            
            let elements = [];
            for (const selector of selectors) {
                const found = document.querySelectorAll(selector);
                if (found.length > 0) {
                    elements = Array.from(found);
                    break;
                }
            }
            
            // 如果没有找到标准结果，尝试其他结构
            if (elements.length === 0) {
                // 查找所有包含链接的div
                const allLinks = document.querySelectorAll('a[href*="http"]');
                const uniqueLinks = new Set();
                
                allLinks.forEach(link => {
                    const href = link.href;
                    const text = link.textContent.trim();
                    
                    // 过滤掉Google内部链接
                    if (href && !href.includes('google.com') && 
                        !href.startsWith('/') && 
                        text.length > 10) {
                        
                        uniqueLinks.add(href);
                        
                        results.push({
                            title: text.substring(0, 200),
                            url: href,
                            snippet: link.closest('div') ? link.closest('div').textContent.substring(0, 300) : '',
                            source: 'fallback'
                        });
                    }
                });
                
                return results.slice(0, 10);
            }
            
            // 处理找到的标准结果
            elements.slice(0, 10).forEach(element => {
                const link = element.querySelector('a[href]');
                if (!link) return;
                
                const title = element.querySelector('h3') || 
                             element.querySelector('[role="heading"]') ||
                             link;
                
                const snippet = element.querySelector('div[data-sncf]') ||
                               element.querySelector('.VwiC3b') ||
                               element.querySelector('.MUxGbd') ||
                               element.querySelector('span[data-tts]');
                
                results.push({
                    title: title ? title.textContent.trim().substring(0, 200) : '',
                    url: link.href,
                    snippet: snippet ? snippet.textContent.trim().substring(0, 300) : '',
                    source: 'standard'
                });
            });
            
            return results;
        });
    } catch (error) {
        console.log(`⚠️  提取搜索结果失败: ${error.message}`);
        return [];
    }
}