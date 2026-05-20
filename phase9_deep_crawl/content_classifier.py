#!/usr/bin/env python3
"""
内容分类器 - 智能网页内容分类和信息提取
专门为岗位网站优化，识别页面类型、提取关键信息、质量评估
"""

import re
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
import logging
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

@dataclass
class ContentFeatures:
    """内容特征"""
    word_count: int = 0
    link_count: int = 0
    form_count: int = 0
    job_keyword_count: int = 0
    salary_mention: bool = False
    location_mention: bool = False
    qualification_mention: bool = False
    apply_button: bool = False
    date_mention: bool = False
    company_mention: bool = False
    
    # 结构特征
    has_table: bool = False
    has_list: bool = False
    has_section_headings: bool = False
    has_contact_info: bool = False
    
    # URL特征
    url_contains_job: bool = False
    url_contains_career: bool = False
    url_contains_apply: bool = False
    url_contains_detail: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items()}
    
    @classmethod
    def from_html(cls, html: str, url: str) -> 'ContentFeatures':
        """从HTML提取特征"""
        features = cls()
        
        # 文本内容（简单提取）
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 基本特征
        features.word_count = len(text.split())
        
        # 链接计数
        features.link_count = len(re.findall(r'<a[^>]*>', html, re.IGNORECASE))
        
        # 表单计数
        features.form_count = len(re.findall(r'<form[^>]*>', html, re.IGNORECASE))
        
        # 关键词检测
        text_lower = text.lower()
        url_lower = url.lower()
        
        # 职位关键词
        job_keywords = [
            'job', 'career', 'position', 'vacancy', 'employment',
            'opportunity', 'opening', 'role', 'post', 'appointment',
            'recruitment', 'hiring', 'staff', 'employee', 'talent',
            'work', 'profession', 'occupation'
        ]
        
        features.job_keyword_count = sum(1 for keyword in job_keywords 
                                        if keyword in text_lower)
        
        # 其他特征
        features.salary_mention = any(word in text_lower 
                                     for word in ['salary', 'pay', 'wage', 'compensation', '$'])
        features.location_mention = any(word in text_lower 
                                       for word in ['location', 'address', 'city', 'state', 'country'])
        features.qualification_mention = any(word in text_lower 
                                           for word in ['qualification', 'requirement', 'experience', 'skill', 'education'])
        features.apply_button = any(word in text_lower 
                                   for word in ['apply', 'application', 'submit', 'send', 'upload'])
        features.date_mention = any(word in text_lower 
                                   for word in ['date', 'deadline', 'closing', 'posted'])
        features.company_mention = any(word in text_lower 
                                      for word in ['company', 'employer', 'organization', 'firm', 'corporation'])
        
        # 结构特征
        features.has_table = '<table' in html.lower()
        features.has_list = any(tag in html.lower() 
                               for tag in ['<ul>', '<ol>', '<li>'])
        features.has_section_headings = any(tag in html.lower() 
                                          for tag in ['<h1>', '<h2>', '<h3>', '<h4>'])
        features.has_contact_info = any(word in text_lower 
                                       for word in ['contact', 'phone', 'email', 'tel:', 'mailto:'])
        
        # URL特征
        features.url_contains_job = 'job' in url_lower
        features.url_contains_career = 'career' in url_lower
        features.url_contains_apply = 'apply' in url_lower
        features.url_contains_detail = any(word in url_lower 
                                         for word in ['detail', 'view', 'show', 'id='])
        
        return features

@dataclass
class ClassifiedContent:
    """分类后的内容"""
    url: str
    page_type: str  # job_list, job_detail, application_form, company_page, other
    confidence: float  # 0-1，分类置信度
    
    # 提取的信息
    title: str = ""
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 特征
    features: Optional[ContentFeatures] = None
    
    # 质量评分
    quality_score: float = 0.0  # 0-100
    
    # 去重信息
    content_hash: str = ""
    similarity_score: float = 0.0  # 与已有内容的相似度
    
    def __post_init__(self):
        # 确保置信度在0-1范围内
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.quality_score = max(0.0, min(100.0, self.quality_score))
        self.similarity_score = max(0.0, min(1.0, self.similarity_score))

class ContentClassifier:
    """内容分类器"""
    
    # 页面类型定义
    PAGE_TYPES = {
        'job_list': {
            'description': '职位列表页',
            'keywords': ['jobs', 'careers', 'vacancies', 'search results', 'open positions'],
            'min_confidence': 0.6
        },
        'job_detail': {
            'description': '职位详情页',
            'keywords': ['job description', 'position details', 'role requirements', 'apply now'],
            'min_confidence': 0.7
        },
        'application_form': {
            'description': '申请表页',
            'keywords': ['application form', 'apply online', 'submit application', 'upload resume'],
            'min_confidence': 0.8
        },
        'company_page': {
            'description': '公司信息页',
            'keywords': ['about us', 'company profile', 'our team', 'mission statement'],
            'min_confidence': 0.6
        },
        'other': {
            'description': '其他页面',
            'keywords': [],
            'min_confidence': 0.0
        }
    }
    
    # 网站特定规则
    WEBSITE_RULES = {
        'indeed': {
            'job_list_selectors': ['.job_seen_beacon', '.jobsearch-SerpJobCard'],
            'job_detail_selectors': ['.jobsearch-JobComponent', '.jobDescriptionText'],
            'application_selectors': ['.applyButton', '.indeed-apply-button'],
            'company_selectors': ['.icl-u-lg-mr--sm', '.companyName']
        },
        'seek': {
            'job_list_selectors': ['[data-automation="normalJob"]', '[data-automation="searchResult"]'],
            'job_detail_selectors': ['[data-automation="job-details"]', '.FYwKg _2j_7Q _3VEKP'],
            'application_selectors': ['[data-automation="applyNowButton"]', '.apply-button'],
            'company_selectors': ['[data-automation="advertiser-name"]']
        },
        'aps': {
            'job_list_selectors': ['.job-listing-item', '.vacancy-item'],
            'job_detail_selectors': ['.job-description', '.position-details'],
            'application_selectors': ['.apply-button', '.application-form'],
            'company_selectors': ['.agency-name', '.department-info']
        }
    }
    
    def __init__(self, custom_rules: Optional[Dict] = None):
        """初始化内容分类器"""
        self.classified_contents: Dict[str, ClassifiedContent] = {}  # URL -> 分类内容
        self.content_hashes: Set[str] = set()  # 内容哈希集合（用于去重）
        
        # 更新规则
        if custom_rules:
            self.WEBSITE_RULES.update(custom_rules)
        
        logger.info(f"内容分类器初始化完成，支持 {len(self.PAGE_TYPES)} 种页面类型")
    
    def classify_content(self, html: str, url: str, 
                        website_type: Optional[str] = None) -> ClassifiedContent:
        """
        分类网页内容
        
        Args:
            html: HTML内容
            url: 页面URL
            website_type: 网站类型（indeed, seek, aps等）
            
        Returns:
            分类后的内容
        """
        # 提取特征
        features = ContentFeatures.from_html(html, url)
        
        # 检测页面类型
        page_type, confidence = self._detect_page_type(html, url, features, website_type)
        
        # 提取标题和摘要
        title = self._extract_title(html)
        summary = self._extract_summary(html)
        
        # 计算质量评分
        quality_score = self._calculate_quality_score(features, page_type)
        
        # 计算内容哈希（用于去重）
        content_hash = self._calculate_content_hash(html)
        
        # 计算相似度
        similarity_score = self._calculate_similarity(content_hash)
        
        # 创建分类结果
        classified = ClassifiedContent(
            url=url,
            page_type=page_type,
            confidence=confidence,
            title=title,
            summary=summary,
            features=features,
            quality_score=quality_score,
            content_hash=content_hash,
            similarity_score=similarity_score,
            metadata=self._extract_metadata(html, url, website_type)
        )
        
        # 缓存结果
        self.classified_contents[url] = classified
        self.content_hashes.add(content_hash)
        
        logger.debug(f"内容分类完成: {url} -> {page_type} (置信度: {confidence:.2f})")
        
        return classified
    
    def _detect_page_type(self, html: str, url: str, 
                         features: ContentFeatures,
                         website_type: Optional[str]) -> Tuple[str, float]:
        """检测页面类型"""
        scores = {}
        url_lower = url.lower()
        html_lower = html.lower()
        
        # 检查URL特征
        if 'apply' in url_lower or 'application' in url_lower:
            scores['application_form'] = 0.8
        
        if 'job' in url_lower and ('detail' in url_lower or 'view' in url_lower or 'id=' in url_lower):
            scores['job_detail'] = 0.7
        
        if 'jobs' in url_lower or 'careers' in url_lower or 'vacancies' in url_lower:
            scores['job_list'] = 0.6
        
        # 检查HTML特征
        text = re.sub(r'<[^>]+>', ' ', html)
        text_lower = text.lower()
        
        # 职位列表页特征
        list_indicators = [
            ('search results', 0.3),
            ('found \d+ jobs', 0.4),
            ('page \d+ of', 0.3),
            ('next page', 0.3),
            ('previous page', 0.2),
            ('sort by', 0.2),
            ('filter', 0.2)
        ]
        
        list_score = 0.0
        for indicator, weight in list_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                list_score += weight
        
        if list_score > 0:
            scores['job_list'] = max(scores.get('job_list', 0), min(0.9, list_score))
        
        # 职位详情页特征
        detail_indicators = [
            ('job description', 0.4),
            ('position details', 0.3),
            ('key responsibilities', 0.3),
            ('qualifications', 0.3),
            ('requirements', 0.3),
            ('skills required', 0.3),
            ('about the role', 0.3),
            ('salary', 0.2),
            ('location', 0.2)
        ]
        
        detail_score = 0.0
        for indicator, weight in detail_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                detail_score += weight
        
        if detail_score > 0:
            scores['job_detail'] = max(scores.get('job_detail', 0), min(0.9, detail_score))
        
        # 申请表特征
        form_indicators = [
            ('application form', 0.5),
            ('apply now', 0.4),
            ('submit application', 0.4),
            ('upload resume', 0.3),
            ('cv', 0.2),
            ('cover letter', 0.2),
            ('personal details', 0.2),
            ('<form', 0.3),
            ('<input', 0.2),
            ('<select', 0.2),
            ('<textarea', 0.2)
        ]
        
        form_score = 0.0
        for indicator, weight in form_indicators:
            if indicator in html_lower or indicator in text_lower:
                form_score += weight
        
        if form_score > 0:
            scores['application_form'] = max(scores.get('application_form', 0), min(0.95, form_score))
        
        # 公司页面特征
        company_indicators = [
            ('about us', 0.4),
            ('company profile', 0.3),
            ('our mission', 0.3),
            ('our team', 0.3),
            ('our values', 0.2),
            ('history', 0.2),
            ('leadership', 0.2)
        ]
        
        company_score = 0.0
        for indicator, weight in company_indicators:
            if indicator in text_lower:
                company_score += weight
        
        if company_score > 0:
            scores['company_page'] = max(scores.get('company_page', 0), min(0.9, company_score))
        
        # 使用特征工程
        feature_scores = self._calculate_feature_scores(features)
        for page_type, score in feature_scores.items():
            scores[page_type] = max(scores.get(page_type, 0), score)
        
        # 应用网站特定规则
        if website_type in self.WEBSITE_RULES:
            website_scores = self._apply_website_rules(html, website_type)
            for page_type, score in website_scores.items():
                scores[page_type] = max(scores.get(page_type, 0), score)
        
        # 如果没有明显的类型，根据内容长度判断
        if not scores:
            if features.word_count > 800:
                scores['job_detail'] = 0.5
            elif features.word_count > 200:
                scores['job_list'] = 0.4
            else:
                scores['other'] = 0.3
        
        # 确保至少有一个类型
        if not scores:
            scores['other'] = 0.1
        
        # 选择得分最高的类型
        best_type = max(scores.items(), key=lambda x: x[1])
        
        return best_type[0], best_type[1]
    
    def _calculate_feature_scores(self, features: ContentFeatures) -> Dict[str, float]:
        """根据特征计算页面类型得分"""
        scores = {}
        
        # 职位列表页特征
        list_score = 0.0
        if features.link_count > 10:
            list_score += 0.3
        if features.word_count > 100 and features.word_count < 1000:
            list_score += 0.2
        if features.job_keyword_count > 2:
            list_score += 0.2
        
        if list_score > 0:
            scores['job_list'] = min(0.8, list_score)
        
        # 职位详情页特征
        detail_score = 0.0
        if features.word_count > 500:
            detail_score += 0.3
        if features.job_keyword_count > 5:
            detail_score += 0.3
        if features.qualification_mention:
            detail_score += 0.2
        if features.location_mention:
            detail_score += 0.1
        if features.salary_mention:
            detail_score += 0.1
        
        if detail_score > 0:
            scores['job_detail'] = min(0.9, detail_score)
        
        # 申请表特征
        form_score = 0.0
        if features.form_count > 0:
            form_score += 0.4
        if features.apply_button:
            form_score += 0.3
        if features.word_count > 200 and features.word_count < 800:
            form_score += 0.2
        
        if form_score > 0:
            scores['application_form'] = min(0.9, form_score)
        
        # 公司页面特征
        company_score = 0.0
        if features.company_mention and features.word_count > 300:
            company_score += 0.3
        if features.has_contact_info:
            company_score += 0.2
        if not features.job_keyword_count and features.word_count > 200:
            company_score += 0.2
        
        if company_score > 0:
            scores['company_page'] = min(0.8, company_score)
        
        return scores
    
    def _apply_website_rules(self, html: str, website_type: str) -> Dict[str, float]:
        """应用网站特定规则"""
        scores = {}
        
        if website_type not in self.WEBSITE_RULES:
            return scores
        
        rules = self.WEBSITE_RULES[website_type]
        html_lower = html.lower()
        
        # 检查选择器模式
        for page_type in ['job_list', 'job_detail', 'application_form', 'company_page']:
            selectors = rules.get(f'{page_type}_selectors', [])
            for selector in selectors:
                # 简化检查：查找选择器中的特征词
                selector_words = re.findall(r'[a-zA-Z]+', selector)
                for word in selector_words:
                    if word.lower() in html_lower:
                        scores[page_type] = max(scores.get(page_type, 0), 0.5)
                        break
        
        return scores
    
    def _extract_title(self, html: str) -> str:
        """提取页面标题"""
        # 从<title>标签提取
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if title:
                return title[:200]  # 限制长度
        
        # 从<h1>标签提取
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if h1_match:
            title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
            if title:
                return title[:150]
        
        # 从og:title或twitter:title元标签提取
        meta_patterns = [
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']',
            r'<meta[^>]*name=["\']twitter:title["\'][^>]*content=["\'](.*?)["\']'
        ]
        
        for pattern in meta_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if title:
                    return title[:200]
        
        return ""
    
    def _extract_summary(self, html: str, max_length: int = 300) -> str:
        """提取内容摘要"""
        # 移除脚本和样式
        html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
        
        # 提取正文文本
        text = re.sub(r'<[^>]+>', ' ', html_clean)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 提取前N个字符作为摘要
        if len(text) <= max_length:
            return text
        
        # 尝试在句子边界处截断
        sentences = re.split(r'[.!?]', text[:max_length * 2])
        if len(sentences) > 1:
            # 取完整的句子
            summary = '.'.join(sentences[:-1]) + '.'
            if len(summary) <= max_length:
                return summary
        
        # 在单词边界处截断
        if len(text) > max_length:
            truncated = text[:max_length]
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.8:  # 确保截断点不太靠前
                return truncated[:last_space] + '...'
        
        return text[:max_length] + '...'
    
    def _extract_metadata(self, html: str, url: str, 
                         website_type: Optional[str]) -> Dict[str, Any]:
        """提取元数据"""
        metadata = {
            'url': url,
            'website_type': website_type or 'unknown',
            'extraction_time': self._get_current_timestamp()
        }
        
        # 提取<meta>标签
        meta_pattern = r'<meta[^>]*>'
        for match in re.finditer(meta_pattern, html, re.IGNORECASE):
            meta_tag = match.group(0)
            
            # 提取属性
            name_match = re.search(r'name=["\']([^"\']+)["\']', meta_tag, re.IGNORECASE)
            property_match = re.search(r'property=["\']([^"\']+)["\']', meta_tag, re.IGNORECASE)
            content_match = re.search(r'content=["\']([^"\']+)["\']', meta_tag, re.IGNORECASE)
            
            key = None
            if name_match:
                key = f"meta:{name_match.group(1).lower()}"
            elif property_match:
                key = f"property:{property_match.group(1).lower()}"
            
            if key and content_match:
                metadata[key] = content_match.group(1)
        
        # 提取其他有用信息
        # 1. 语言
        lang_match = re.search(r'<html[^>]*lang=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if lang_match:
            metadata['language'] = lang_match.group(1)
        
        # 2. 字符编码
        charset_match = re.search(r'charset=["\']?([^"\'\s>]+)', html, re.IGNORECASE)
        if charset_match:
            metadata['charset'] = charset_match.group(1)
        
        # 3. 生成器（如WordPress）
        generator_match = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']+)["\']', 
                                   html, re.IGNORECASE)
        if generator_match:
            metadata['generator'] = generator_match.group(1)
        
        return metadata
    
    def _calculate_quality_score(self, features: ContentFeatures, 
                               page_type: str) -> float:
        """计算内容质量评分"""
        score = 0.0
        
        # 基础评分
        if features.word_count > 0:
            # 内容长度评分（0-30分）
            length_score = min(30, features.word_count / 10)
            score += length_score
        
        # 页面类型特定评分
        if page_type == 'job_detail':
            # 职位详情页应该包含更多信息
            if features.qualification_mention:
                score += 15
            if features.location_mention:
                score += 10
            if features.salary_mention:
                score += 10
            if features.company_mention:
                score += 5
            
            # 结构特征
            if features.has_list or features.has_table:
                score += 10
            if features.has_section_headings:
                score += 5
        
        elif page_type == 'job_list':
            # 职位列表页应该有多个链接
            if features.link_count > 5:
                score += min(20, features.link_count * 2)
            
            # 应该包含职位关键词
            if features.job_keyword_count > 0:
                score += min(15, features.job_keyword_count * 3)
        
        elif page_type == 'application_form':
            # 申请表应该有表单元素
            if features.form_count > 0:
                score += 20
            
            if features.apply_button:
                score += 15
        
        # 通用质量指标
        if features.job_keyword_count > 0:
            score += min(20, features.job_keyword_count * 4)
        
        if features.has_contact_info:
            score += 5
        
        # 确保评分在0-100范围内
        return min(100.0, max(0.0, score))
    
    def _calculate_content_hash(self, html: str) -> str:
        """计算内容哈希（用于去重）"""
        # 提取主要文本内容
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 取前1000个字符（避免太长）
        if len(text) > 1000:
            text = text[:1000]
        
        # 计算MD5哈希
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _calculate_similarity(self, content_hash: str) -> float:
        """计算与已有内容的相似度"""
        if content_hash in self.content_hashes:
            return 1.0  # 完全相同的哈希值
        
        # 这里可以实现更复杂的相似度计算
        # 当前使用简单的哈希匹配
        return 0.0
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def is_duplicate_content(self, html: str, threshold: float = 0.8) -> bool:
        """检查是否是重复内容"""
        content_hash = self._calculate_content_hash(html)
        similarity = self._calculate_similarity(content_hash)
        
        return similarity >= threshold
    
    def filter_by_quality(self, contents: List[ClassifiedContent],
                         min_quality: float = 30.0) -> List[ClassifiedContent]:
        """按质量过滤内容"""
        return [content for content in contents 
                if content.quality_score >= min_quality]
    
    def filter_by_confidence(self, contents: List[ClassifiedContent],
                            min_confidence: float = 0.6) -> List[ClassifiedContent]:
        """按置信度过滤内容"""
        return [content for content in contents 
                if content.confidence >= min_confidence]
    
    def filter_duplicates(self, contents: List[ClassifiedContent],
                         similarity_threshold: float = 0.8) -> List[ClassifiedContent]:
        """过滤重复内容"""
        unique_contents = []
        seen_hashes = set()
        
        for content in contents:
            if content.content_hash not in seen_hashes:
                seen_hashes.add(content.content_hash)
                unique_contents.append(content)
            else:
                logger.debug(f"跳过重复内容: {content.url}")
        
        return unique_contents
    
    def analyze_contents(self, contents: List[ClassifiedContent]) -> Dict[str, Any]:
        """分析内容集合"""
        analysis = {
            'total_contents': len(contents),
            'by_page_type': defaultdict(int),
            'quality_stats': {
                'min': float('inf'),
                'max': float('-inf'),
                'avg': 0.0,
                'std': 0.0
            },
            'confidence_stats': {
                'min': float('inf'),
                'max': float('-inf'),
                'avg': 0.0,
                'std': 0.0
            },
            'feature_summary': defaultdict(int)
        }
        
        if not contents:
            return analysis
        
        # 按页面类型统计
        for content in contents:
            analysis['by_page_type'][content.page_type] += 1
        
        # 质量统计
        quality_scores = [content.quality_score for content in contents]
        analysis['quality_stats']['min'] = min(quality_scores)
        analysis['quality_stats']['max'] = max(quality_scores)
        analysis['quality_stats']['avg'] = sum(quality_scores) / len(quality_scores)
        
        # 计算标准差
        if len(quality_scores) > 1:
            mean = analysis['quality_stats']['avg']
            variance = sum((x - mean) ** 2 for x in quality_scores) / (len(quality_scores) - 1)
            analysis['quality_stats']['std'] = math.sqrt(variance)
        
        # 置信度统计
        confidence_scores = [content.confidence for content in contents]
        analysis['confidence_stats']['min'] = min(confidence_scores)
        analysis['confidence_stats']['max'] = max(confidence_scores)
        analysis['confidence_stats']['avg'] = sum(confidence_scores) / len(confidence_scores)
        
        if len(confidence_scores) > 1:
            mean = analysis['confidence_stats']['avg']
            variance = sum((x - mean) ** 2 for x in confidence_scores) / (len(confidence_scores) - 1)
            analysis['confidence_stats']['std'] = math.sqrt(variance)
        
        # 特征摘要（如果有特征）
        if contents[0].features:
            feature_counts = defaultdict(int)
            for content in contents:
                if content.features:
                    features_dict = content.features.to_dict()
                    for key, value in features_dict.items():
                        if isinstance(value, bool) and value:
                            feature_counts[key] += 1
                        elif isinstance(value, (int, float)) and value > 0:
                            feature_counts[key] += 1
            
            analysis['feature_summary'] = dict(feature_counts)
        
        return analysis
    
    def export_classified_contents(self, contents: List[ClassifiedContent],
                                  output_file: str) -> Dict[str, Any]:
        """导出分类后的内容"""
        import json
        
        export_data = []
        for content in contents:
            content_dict = {
                'url': content.url,
                'page_type': content.page_type,
                'confidence': content.confidence,
                'title': content.title,
                'summary': content.summary,
                'quality_score': content.quality_score,
                'content_hash': content.content_hash,
                'similarity_score': content.similarity_score,
                'metadata': content.metadata
            }
            
            if content.features:
                content_dict['features'] = content.features.to_dict()
            
            export_data.append(content_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        # 分析报告
        analysis = self.analyze_contents(contents)
        
        report_file = output_file.replace('.json', '_report.json')
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        logger.info(f"导出 {len(export_data)} 个分类内容到 {output_file}")
        
        return {
            'data_file': output_file,
            'report_file': report_file,
            'total_contents': len(export_data),
            'analysis': analysis
        }