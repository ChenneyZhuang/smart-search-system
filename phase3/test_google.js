#!/usr/bin/env node
/**
 * 快速测试Google搜索增强版
 */

const { execSync } = require('child_process');
const path = require('path');

const scriptPath = path.join(__dirname, 'google_search_enhanced.js');
const query = 'OpenClaw AI';

console.log('🧪 测试Google增强爬取器...');
console.log(`查询: "${query}"`);

try {
    // 使用headless模式测试
    process.env.HEADLESS_TEST = 'true';
    
    const startTime = Date.now();
    
    // 运行脚本（带超时）
    const result = execSync(
        `node "${scriptPath}" "" "${query}"`,
        { 
            encoding: 'utf8',
            timeout: 45000, // 45秒超时
            stdio: ['pipe', 'pipe', 'pipe']
        }
    );
    
    const elapsed = (Date.now() - startTime) / 1000;
    
    console.log(`✅ 测试成功 (${elapsed.toFixed(1)}s)`);
    
    // 尝试解析结果
    try {
        const lines = result.split('\n');
        const jsonLine = lines.find(line => line.trim().startsWith('{'));
        if (jsonLine) {
            const data = JSON.parse(jsonLine);
            console.log(`📊 结果摘要:`);
            console.log(`   成功: ${data.success}`);
            console.log(`   耗时: ${data.elapsedSeconds}s`);
            console.log(`   搜索结果数: ${data.searchResults ? data.searchResults.length : 0}`);
            console.log(`   反爬检测: ${data.pageInfo ? data.pageInfo.detectedAntiBot : '未知'}`);
        } else {
            console.log('📄 原始输出预览:');
            console.log(result.substring(0, 500) + '...');
        }
    } catch (parseError) {
        console.log('📄 输出不是JSON，显示最后1000字符:');
        console.log(result.substring(result.length - 1000));
    }
    
} catch (error) {
    console.error('❌ 测试失败:');
    console.error(`   错误: ${error.message}`);
    
    if (error.signal) {
        console.error(`   信号: ${error.signal} (可能超时或被中断)`);
    }
    
    if (error.stderr) {
        console.error('   STDERR:');
        console.error(error.stderr.toString().substring(0, 500));
    }
    
    process.exit(1);
}