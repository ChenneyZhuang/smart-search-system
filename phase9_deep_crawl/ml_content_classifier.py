#!/usr/bin/env python3
"""
机器学习内容分类器 - 使用ML模型智能分类网页内容
支持训练、预测和模型评估，专门为岗位网站优化
"""

import json
import pickle
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
import logging
from pathlib import Path
import hashlib
from datetime import datetime
import os

logger = logging.getLogger(__name__)

@dataclass
class TrainingExample:
    """训练示例"""
    features: Dict[str, Union[float, int, bool]]
    label: str  # 页面类型：job_list, job_detail, application_form, company_page, other
    url: str = ""
    confidence: float = 1.0
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_feature_vector(self, feature_names: List[str]) -> List[float]:
        """转换为特征向量"""
        vector = []
        for name in feature_names:
            value = self.features.get(name, 0.0)
            # 转换为浮点数
            if isinstance(value, bool):
                vector.append(1.0 if value else 0.0)
            else:
                vector.append(float(value))
        return vector

@dataclass
class ModelMetrics:
    """模型评估指标"""
    accuracy: float = 0.0
    precision: Dict[str, float] = field(default_factory=dict)
    recall: Dict[str, float] = field(default_factory=dict)
    f1_score: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: List[List[int]] = field(default_factory=list)
    training_time_seconds: float = 0.0
    inference_time_seconds: float = 0.0
    model_size_bytes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

class MLContentClassifier:
    """机器学习内容分类器"""
    
    # 支持的页面类型
    PAGE_TYPES = ['job_list', 'job_detail', 'application_form', 'company_page', 'other']
    
    # 特征名称（根据ContentFeatures定义）
    FEATURE_NAMES = [
        'word_count', 'link_count', 'form_count', 'job_keyword_count',
        'salary_mention', 'location_mention', 'qualification_mention',
        'apply_button', 'date_mention', 'company_mention',
        'has_table', 'has_list', 'has_section_headings', 'has_contact_info',
        'url_contains_job', 'url_contains_career', 'url_contains_apply',
        'url_contains_detail'
    ]
    
    def __init__(self, model_dir: str = "./ml_models", use_ml: bool = True):
        """
        初始化ML分类器
        
        Args:
            model_dir: 模型保存目录
            use_ml: 是否使用ML模型（如果为False则使用规则引擎）
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.use_ml = use_ml
        self.model = None
        self.feature_names = self.FEATURE_NAMES
        self.label_encoder = None
        
        # 训练数据
        self.training_examples: List[TrainingExample] = []
        
        # 模型指标
        self.metrics = ModelMetrics()
        
        # 尝试导入ML库
        self.ml_available = self._check_ml_availability()
        
        if not self.ml_available and use_ml:
            logger.warning("ML库不可用，将使用规则引擎")
            self.use_ml = False
        
        logger.info(f"ML分类器初始化完成，ML可用: {self.ml_available}, 使用ML: {self.use_ml}")
    
    def _check_ml_availability(self) -> bool:
        """检查ML库是否可用"""
        try:
            # 尝试导入常用ML库
            import sklearn
            import numpy as np
            return True
        except ImportError:
            logger.warning("scikit-learn不可用，ML功能将受限")
            return False
    
    def load_training_data(self, filepath: str) -> bool:
        """加载训练数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data:
                example = TrainingExample(
                    features=item['features'],
                    label=item['label'],
                    url=item.get('url', ''),
                    confidence=item.get('confidence', 1.0)
                )
                self.training_examples.append(example)
            
            logger.info(f"加载 {len(self.training_examples)} 个训练示例")
            return True
            
        except Exception as e:
            logger.error(f"加载训练数据失败: {e}")
            return False
    
    def add_training_example(self, features: Dict[str, Any], label: str, 
                           url: str = "", confidence: float = 1.0):
        """添加训练示例"""
        example = TrainingExample(
            features=features,
            label=label,
            url=url,
            confidence=confidence
        )
        self.training_examples.append(example)
    
    def save_training_data(self, filepath: str):
        """保存训练数据"""
        try:
            data = []
            for example in self.training_examples:
                data.append({
                    'features': example.features,
                    'label': example.label,
                    'url': example.url,
                    'confidence': example.confidence,
                    'timestamp': example.timestamp
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"保存 {len(data)} 个训练示例到 {filepath}")
            
        except Exception as e:
            logger.error(f"保存训练数据失败: {e}")
    
    def train_model(self, algorithm: str = "random_forest") -> bool:
        """
        训练ML模型
        
        Args:
            algorithm: 算法类型 (random_forest, logistic_regression, svm, naive_bayes)
            
        Returns:
            是否训练成功
        """
        if not self.ml_available or not self.use_ml:
            logger.warning("ML不可用，跳过训练")
            return False
        
        if len(self.training_examples) < 10:
            logger.warning(f"训练数据不足 ({len(self.training_examples)} 个示例)，至少需要10个")
            return False
        
        import time
        start_time = time.time()
        
        try:
            import numpy as np
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import LabelEncoder
            from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
            
            # 准备数据
            X = []
            y = []
            
            for example in self.training_examples:
                X.append(example.to_feature_vector(self.feature_names))
                y.append(example.label)
            
            X = np.array(X)
            y = np.array(y)
            
            # 编码标签
            self.label_encoder = LabelEncoder()
            y_encoded = self.label_encoder.fit_transform(y)
            
            # 分割训练测试集
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
            )
            
            # 训练模型
            if algorithm == "random_forest":
                from sklearn.ensemble import RandomForestClassifier
                self.model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42,
                    class_weight='balanced'
                )
            
            elif algorithm == "logistic_regression":
                from sklearn.linear_model import LogisticRegression
                self.model = LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                    class_weight='balanced'
                )
            
            elif algorithm == "svm":
                from sklearn.svm import SVC
                self.model = SVC(
                    kernel='rbf',
                    probability=True,
                    random_state=42,
                    class_weight='balanced'
                )
            
            elif algorithm == "naive_bayes":
                from sklearn.naive_bayes import GaussianNB
                self.model = GaussianNB()
            
            else:
                logger.error(f"未知算法: {algorithm}")
                return False
            
            self.model.fit(X_train, y_train)
            
            # 评估模型
            y_pred = self.model.predict(X_test)
            y_pred_labels = self.label_encoder.inverse_transform(y_pred)
            y_test_labels = self.label_encoder.inverse_transform(y_test)
            
            # 计算指标
            self.metrics.accuracy = accuracy_score(y_test, y_pred)
            
            # 分类报告
            report = classification_report(y_test_labels, y_pred_labels, 
                                         target_names=self.PAGE_TYPES,
                                         output_dict=True)
            
            for label in self.PAGE_TYPES:
                if label in report:
                    self.metrics.precision[label] = report[label]['precision']
                    self.metrics.recall[label] = report[label]['recall']
                    self.metrics.f1_score[label] = report[label]['f1-score']
            
            # 混淆矩阵
            cm = confusion_matrix(y_test, y_pred)
            self.metrics.confusion_matrix = cm.tolist()
            
            # 时间和大小
            self.metrics.training_time_seconds = time.time() - start_time
            
            # 测试推理时间
            inference_start = time.time()
            _ = self.model.predict(X_test[:10])
            self.metrics.inference_time_seconds = (time.time() - inference_start) / 10
            
            # 模型大小
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                pickle.dump(self.model, tmp)
                self.metrics.model_size_bytes = os.path.getsize(tmp.name)
                os.unlink(tmp.name)
            
            logger.info(f"模型训练完成，准确率: {self.metrics.accuracy:.3f}")
            logger.info(f"训练时间: {self.metrics.training_time_seconds:.2f}秒")
            logger.info(f"推理时间: {self.metrics.inference_time_seconds:.4f}秒/样本")
            
            return True
            
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def predict(self, features: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """
        预测页面类型
        
        Args:
            features: 特征字典
            
        Returns:
            (预测类型, 置信度, 所有类型的概率)
        """
        if self.use_ml and self.model is not None:
            return self._predict_ml(features)
        else:
            return self._predict_rule_based(features)
    
    def _predict_ml(self, features: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """使用ML模型预测"""
        try:
            # 转换为特征向量
            feature_vector = []
            for name in self.feature_names:
                value = features.get(name, 0.0)
                if isinstance(value, bool):
                    feature_vector.append(1.0 if value else 0.0)
                else:
                    feature_vector.append(float(value))
            
            X = np.array([feature_vector])
            
            # 预测概率
            probabilities = self.model.predict_proba(X)[0]
            
            # 获取预测标签
            predicted_idx = np.argmax(probabilities)
            predicted_label = self.label_encoder.inverse_transform([predicted_idx])[0]
            confidence = float(probabilities[predicted_idx])
            
            # 所有类型的概率
            all_probabilities = {}
            for i, label in enumerate(self.label_encoder.classes_):
                all_probabilities[label] = float(probabilities[i])
            
            return predicted_label, confidence, all_probabilities
            
        except Exception as e:
            logger.error(f"ML预测失败: {e}")
            # 回退到规则引擎
            return self._predict_rule_based(features)
    
    def _predict_rule_based(self, features: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """使用基于规则的预测（备用）"""
        # 基于规则的简单分类
        scores = {}
        
        # 职位详情页规则
        detail_score = 0.0
        if features.get('word_count', 0) > 500:
            detail_score += 0.3
        if features.get('job_keyword_count', 0) > 3:
            detail_score += 0.3
        if features.get('qualification_mention', False):
            detail_score += 0.2
        if features.get('location_mention', False):
            detail_score += 0.1
        scores['job_detail'] = min(0.9, detail_score)
        
        # 职位列表页规则
        list_score = 0.0
        if features.get('link_count', 0) > 5:
            list_score += 0.3
        if 100 < features.get('word_count', 0) < 1000:
            list_score += 0.2
        if features.get('job_keyword_count', 0) > 0:
            list_score += 0.2
        scores['job_list'] = min(0.8, list_score)
        
        # 申请表规则
        form_score = 0.0
        if features.get('form_count', 0) > 0:
            form_score += 0.4
        if features.get('apply_button', False):
            form_score += 0.3
        scores['application_form'] = min(0.9, form_score)
        
        # 公司页面规则
        company_score = 0.0
        if features.get('company_mention', False) and features.get('word_count', 0) > 300:
            company_score += 0.3
        if features.get('has_contact_info', False):
            company_score += 0.2
        scores['company_page'] = min(0.8, company_score)
        
        # 其他页面
        other_score = 0.1  # 基础分数
        scores['other'] = other_score
        
        # 选择最高分
        best_type = max(scores.items(), key=lambda x: x[1])
        
        # 计算置信度（归一化）
        total_score = sum(scores.values())
        confidence = best_type[1] / total_score if total_score > 0 else 0.5
        
        # 计算概率分布
        all_probabilities = {}
        for label in self.PAGE_TYPES:
            all_probabilities[label] = scores.get(label, 0.0) / total_score if total_score > 0 else 0.0
        
        return best_type[0], confidence, all_probabilities
    
    def save_model(self, model_name: str = "content_classifier"):
        """保存模型"""
        if not self.model:
            logger.warning("没有模型可保存")
            return False
        
        try:
            import pickle
            
            model_file = self.model_dir / f"{model_name}.pkl"
            with open(model_file, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names,
                    'label_encoder': self.label_encoder,
                    'metrics': self.metrics,
                    'training_examples_count': len(self.training_examples),
                    'saved_at': datetime.now().isoformat()
                }, f)
            
            # 保存指标
            metrics_file = self.model_dir / f"{model_name}_metrics.json"
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"模型保存到: {model_file}")
            logger.info(f"指标保存到: {metrics_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False
    
    def load_model(self, model_name: str = "content_classifier") -> bool:
        """加载模型"""
        try:
            import pickle
            
            model_file = self.model_dir / f"{model_name}.pkl"
            if not model_file.exists():
                logger.warning(f"模型文件不存在: {model_file}")
                return False
            
            with open(model_file, 'rb') as f:
                data = pickle.load(f)
            
            self.model = data['model']
            self.feature_names = data.get('feature_names', self.FEATURE_NAMES)
            self.label_encoder = data['label_encoder']
            self.metrics = data.get('metrics', ModelMetrics())
            
            logger.info(f"模型加载成功: {model_file}")
            logger.info(f"训练示例数: {data.get('training_examples_count', 0)}")
            logger.info(f"准确率: {self.metrics.accuracy:.3f}")
            
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def evaluate_on_dataset(self, test_data: List[TrainingExample]) -> Dict[str, Any]:
        """在测试集上评估模型"""
        if not self.model:
            logger.warning("没有模型可评估")
            return {"error": "模型未训练"}
        
        try:
            import numpy as np
            from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
            
            # 准备数据
            X_test = []
            y_test = []
            
            for example in test_data:
                X_test.append(example.to_feature_vector(self.feature_names))
                y_test.append(example.label)
            
            X_test = np.array(X_test)
            y_test = np.array(y_test)
            
            # 编码标签
            y_test_encoded = self.label_encoder.transform(y_test)
            
            # 预测
            y_pred_encoded = self.model.predict(X_test)
            y_pred = self.label_encoder.inverse_transform(y_pred_encoded)
            
            # 计算指标
            accuracy = accuracy_score(y_test_encoded, y_pred_encoded)
            
            # 分类报告
            report = classification_report(y_test, y_pred, 
                                         target_names=self.PAGE_TYPES,
                                         output_dict=True)
            
            # 混淆矩阵
            cm = confusion_matrix(y_test_encoded, y_pred_encoded)
            
            # 详细结果
            detailed_results = []
            for i, (true_label, pred_label) in enumerate(zip(y_test, y_pred)):
                detailed_results.append({
                    'index': i,
                    'true_label': true_label,
                    'pred_label': pred_label,
                    'correct': true_label == pred_label,
                    'url': test_data[i].url if i < len(test_data) else ""
                })
            
            results = {
                'accuracy': accuracy,
                'report': report,
                'confusion_matrix': cm.tolist(),
                'test_set_size': len(test_data),
                'detailed_results': detailed_results[:20],  # 只返回前20个详细结果
                'per_class_accuracy': {}
            }
            
            # 每类准确率
            for label in self.PAGE_TYPES:
                if label in report:
                    results['per_class_accuracy'][label] = report[label]['precision']
            
            return results
            
        except Exception as e:
            logger.error(f"评估失败: {e}")
            return {"error": str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性（仅适用于某些模型）"""
        if not self.model:
            return {}
        
        try:
            if hasattr(self.model, 'feature_importances_'):
                # 随机森林等
                importances = self.model.feature_importances_
            elif hasattr(self.model, 'coef_'):
                # 逻辑回归等
                importances = np.abs(self.model.coef_[0])
            else:
                return {}
            
            # 创建特征重要性字典
            feature_importance = {}
            for i, name in enumerate(self.feature_names):
                if i < len(importances):
                    feature_importance[name] = float(importances[i])
            
            # 按重要性排序
            sorted_importance = dict(sorted(feature_importance.items(), 
                                          key=lambda x: x[1], reverse=True))
            
            return sorted_importance
            
        except Exception as e:
            logger.error(f"获取特征重要性失败: {e}")
            return {}
    
    def generate_synthetic_training_data(self, num_examples: int = 100) -> bool:
        """生成合成训练数据（用于测试和开发）"""
        import random
        
        try:
            for i in range(num_examples):
                # 生成随机特征
                features = {}
                
                # 根据页面类型生成不同的特征
                page_type = random.choice(self.PAGE_TYPES)
                
                if page_type == 'job_detail':
                    features['word_count'] = random.randint(500, 3000)
                    features['job_keyword_count'] = random.randint(5, 15)
                    features['qualification_mention'] = random.random() > 0.3
                    features['location_mention'] = random.random() > 0.4
                    features['salary_mention'] = random.random() > 0.5
                    features['company_mention'] = random.random() > 0.2
                    features['has_section_headings'] = random.random() > 0.7
                    features['has_list'] = random.random() > 0.6
                
                elif page_type == 'job_list':
                    features['word_count'] = random.randint(100, 800)
                    features['link_count'] = random.randint(10, 50)
                    features['job_keyword_count'] = random.randint(2, 8)
                    features['has_table'] = random.random() > 0.8
                
                elif page_type == 'application_form':
                    features['word_count'] = random.randint(200, 1000)
                    features['form_count'] = random.randint(1, 5)
                    features['apply_button'] = True
                    features['has_contact_info'] = random.random() > 0.5
                
                elif page_type == 'company_page':
                    features['word_count'] = random.randint(300, 2000)
                    features['company_mention'] = True
                    features['has_contact_info'] = random.random() > 0.8
                    features['job_keyword_count'] = random.randint(0, 3)
                
                else:  # other
                    features['word_count'] = random.randint(50, 500)
                    features['job_keyword_count'] = random.randint(0, 2)
                
                # 填充其他特征
                for name in self.feature_names:
                    if name not in features:
                        if 'mention' in name or 'has_' in name or 'contains_' in name:
                            features[name] = random.random() > 0.7
                        elif 'count' in name:
                            features[name] = random.randint(0, 10)
                        else:
                            features[name] = 0.0
                
                self.add_training_example(features, page_type, f"synthetic_{i}")
            
            logger.info(f"生成 {num_examples} 个合成训练示例")
            return True
            
        except Exception as e:
            logger.error(f"生成合成数据失败: {e}")
            return False