#!/usr/bin/env python3
"""
验证码解决器模块
尝试自动解决常见的验证码类型
"""

import os
import re
import time
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import base64
import io
from PIL import Image

# numpy是可选的（用于图像处理）
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("⚠️  numpy未安装，图像验证码解决功能受限")

@dataclass
class CaptchaChallenge:
    """验证码挑战"""
    type: str  # 类型：image_select, text_input, checkbox, etc.
    content: str  # 原始内容
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class CaptchaSolution:
    """验证码解决方案"""
    success: bool
    action: str = ""  # 解决动作：click, type, select, etc.
    value: Any = None  # 解决值：坐标、文本、选择项等
    confidence: float = 0.0
    error: str = ""
    metadata: Dict = None  # 添加metadata字段
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "success": self.success,
            "action": self.action,
            "value": str(self.value) if self.value else "",
            "confidence": self.confidence,
            "error": self.error,
            "metadata": self.metadata
        }

class BaseCaptchaSolver:
    """验证码解决器基类"""
    
    def __init__(self):
        self.name = "base_solver"
        self.supported_types = []
    
    def can_solve(self, challenge: CaptchaChallenge) -> bool:
        """检查是否能解决此类型验证码"""
        return challenge.type in self.supported_types
    
    def solve(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决验证码"""
        raise NotImplementedError

class DuckDuckGoCaptchaSolver(BaseCaptchaSolver):
    """DuckDuckGo鸭子验证码解决器"""
    
    def __init__(self):
        super().__init__()
        self.name = "duckduckgo_solver"
        self.supported_types = ["duck_select", "image_select"]
        
        # 简单的鸭子图像特征（颜色、形状等）
        self.duck_features = {
            "color_ranges": [(200, 255), (180, 220), (0, 100)],  # RGB范围
            "shape_aspect_ratio": (0.8, 1.5),  # 宽高比
        }
    
    def solve(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决DuckDuckGo鸭子验证码"""
        print(f"🦆 尝试解决DuckDuckGo验证码...")
        
        # 检查是否有图像数据
        has_image_data = 'image_data' in challenge.metadata
        has_page_snapshot = 'page_snapshot' in challenge.metadata
        
        # 策略1: 如果有图像数据，尝试图像识别
        if has_image_data:
            try:
                # 获取图像数据
                image_data = challenge.metadata['image_data']
                
                # 尝试识别鸭子
                duck_coordinates = self._find_ducks_in_image(image_data)
                
                if duck_coordinates:
                    print(f"✅ 找到 {len(duck_coordinates)} 个鸭子")
                    return CaptchaSolution(
                        success=True,
                        action="click_multiple",
                        value=duck_coordinates,
                        confidence=0.7  # 中等置信度
                    )
                else:
                    print(f"❌ 未找到鸭子")
                    # 如果找不到，使用智能网格点击
                    grid_coordinates = self._generate_smart_grid_clicks()
                    return CaptchaSolution(
                        success=False,  # 标记为失败，但提供尝试方案
                        action="click_multiple",
                        value=grid_coordinates,
                        confidence=0.3,
                        error="无法可靠识别鸭子，使用智能网格点击"
                    )
                    
            except Exception as e:
                print(f"⚠️  图像处理失败: {e}")
                # 回退到智能网格点击
                grid_coordinates = self._generate_smart_grid_clicks()
                return CaptchaSolution(
                    success=False,
                    action="click_multiple",
                    value=grid_coordinates,
                    confidence=0.2,
                    error=f"图像处理失败: {str(e)}"
                )
        
        # 策略2: 如果有页面快照但无图像数据，尝试从快照提取
        elif has_page_snapshot:
            # 这里可以添加从快照提取图像的逻辑
            # 暂时回退到智能网格点击
            grid_coordinates = self._generate_smart_grid_clicks()
            print(f"⚠️  有页面快照但无图像数据，使用智能网格点击")
            return CaptchaSolution(
                success=False,
                action="click_multiple",
                value=grid_coordinates,
                confidence=0.2,
                error="无图像数据，但有页面快照"
            )
        
        # 策略3: 无图像数据，使用智能回退
        else:
            # 分析验证码内容，尝试推断最佳点击策略
            content = challenge.content.lower()
            
            # 检查是否有网格提示
            grid_hints = [
                "grid", "squares", "boxes", "tiles",
                "网格", "方块", "格子", "九宫格"
            ]
            
            has_grid_hint = any(hint in content for hint in grid_hints)
            
            if has_grid_hint:
                # 使用智能网格点击（3x3网格，但选择有策略的位置）
                smart_coordinates = self._generate_smart_grid_clicks()
                print(f"⚠️  无图像数据，但检测到网格提示，使用智能网格点击")
                return CaptchaSolution(
                    success=False,
                    action="click_multiple",
                    value=smart_coordinates,
                    confidence=0.3,
                    error="无图像数据，基于网格提示推断"
                )
            else:
                # 完全无信息，使用随机点击（最后手段）
                random_coordinates = self._generate_random_clicks()
                print(f"⚠️  无图像数据也无提示，使用随机点击")
                return CaptchaSolution(
                    success=False,
                    action="click_multiple",
                    value=random_coordinates,
                    confidence=0.1,
                    error="无图像数据或有用提示"
                )
    
    def _find_ducks_in_image(self, image_data) -> list:
        """在图像中查找鸭子（简化版本）"""
        # 如果numpy不可用，返回随机点击
        if not NUMPY_AVAILABLE:
            print("⚠️  numpy不可用，使用随机点击作为回退")
            return self._generate_random_clicks()
        
        # 这里使用简单的颜色和形状检测
        # 在实际实现中，可以使用更复杂的图像识别
        
        # 将图像数据转换为PIL Image
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            # 处理data URL
            header, data = image_data.split(',', 1)
            image_bytes = base64.b64decode(data)
        elif isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            # 假设是base64字符串
            try:
                image_bytes = base64.b64decode(image_data)
            except:
                return []
        
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = image.convert('RGB')
            
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 简单的颜色检测（寻找黄色/橙色区域）
            height, width, _ = img_array.shape
            
            # 定义鸭子颜色范围（RGB）
            duck_color_min = np.array([200, 180, 0])
            duck_color_max = np.array([255, 220, 100])
            
            # 创建颜色掩码
            mask = np.all((img_array >= duck_color_min) & (img_array <= duck_color_max), axis=2)
            
            # 寻找连通区域（scipy是可选的）
            try:
                from scipy import ndimage
                labeled_array, num_features = ndimage.label(mask)
                
                duck_coordinates = []
                
                # 分析每个区域
                for i in range(1, num_features + 1):
                    # 获取区域坐标
                    y_coords, x_coords = np.where(labeled_array == i)
                    
                    if len(y_coords) < 50:  # 太小，不是鸭子
                        continue
                    
                    # 计算中心点
                    center_x = int(np.mean(x_coords))
                    center_y = int(np.mean(y_coords))
                    
                    # 添加到结果
                    duck_coordinates.append((center_x, center_y))
                
                return duck_coordinates[:9]  # 最多9个
                
            except ImportError:
                # scipy不可用，使用简单方法
                print("⚠️  scipy不可用，使用简单颜色检测")
                # 简单方法：返回图像中心点
                return [(width // 2, height // 2)]
            
        except Exception as e:
            print(f"图像处理错误: {e}")
            return self._generate_random_clicks()
    
    def _generate_random_clicks(self) -> list:
        """生成随机点击位置（9宫格）"""
        # 假设验证码是3x3网格
        grid_positions = []
        for i in range(3):
            for j in range(3):
                # 生成每个格子的中心坐标（假设图像是300x300）
                x = 50 + j * 100
                y = 50 + i * 100
                grid_positions.append((x, y))
        
        # 随机选择3-6个位置
        import random
        num_clicks = random.randint(3, 6)
        random.shuffle(grid_positions)
        
        return grid_positions[:num_clicks]
    
    def _generate_smart_grid_clicks(self) -> list:
        """生成智能网格点击位置（基于常见模式）"""
        # 鸭子验证码的常见模式：鸭子通常出现在某些位置更频繁
        # 基于观察：鸭子通常不会在边缘角落，更可能在中间区域
        
        # 网格位置及其权重（中心区域权重更高）
        grid_weights = [
            # (x, y, weight) - 权重越高越可能被选中
            (50, 50, 1),   # 左上 - 低
            (150, 50, 2),  # 中上 - 中
            (250, 50, 1),  # 右上 - 低
            (50, 150, 2),  # 左中 - 中
            (150, 150, 3), # 中心 - 高
            (250, 150, 2), # 右中 - 中
            (50, 250, 1),  # 左下 - 低
            (150, 250, 2), # 中下 - 中
            (250, 250, 1), # 右下 - 低
        ]
        
        import random
        
        # 根据权重选择位置
        positions = []
        weights = [w for _, _, w in grid_weights]
        
        # 选择4-5个位置（鸭子通常4-5个）
        num_clicks = random.randint(4, 5)
        
        # 加权随机选择
        selected_indices = []
        for _ in range(num_clicks):
            # 排除已选位置
            available_indices = [i for i in range(len(grid_weights)) if i not in selected_indices]
            if not available_indices:
                break
                
            available_weights = [weights[i] for i in available_indices]
            
            # 加权随机选择
            selected = random.choices(available_indices, weights=available_weights, k=1)[0]
            selected_indices.append(selected)
            
            x, y, _ = grid_weights[selected]
            positions.append((x, y))
        
        # 按位置排序（左上到右下）
        positions.sort(key=lambda p: (p[1], p[0]))
        
        return positions

class TextCaptchaSolver(BaseCaptchaSolver):
    """文本验证码解决器"""
    
    def __init__(self):
        super().__init__()
        self.name = "text_solver"
        self.supported_types = ["text_input", "math_problem"]
        
        # 常见数学问题模式
        self.math_patterns = [
            r'(\d+)\s*\+\s*(\d+)',
            r'(\d+)\s*-\s*(\d+)',
            r'(\d+)\s*\*\s*(\d+)',
            r'(\d+)\s*/\s*(\d+)',
            r'(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)',
        ]
    
    def solve(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决文本验证码"""
        print(f"📝 尝试解决文本验证码...")
        
        content = challenge.content.lower()
        
        # 尝试解决数学问题
        math_solution = self._solve_math_problem(content)
        if math_solution:
            return CaptchaSolution(
                success=True,
                action="type",
                value=str(math_solution),
                confidence=0.9
            )
        
        # 尝试识别简单问题
        simple_solution = self._solve_simple_question(content)
        if simple_solution:
            return CaptchaSolution(
                success=True,
                action="type",
                value=simple_solution,
                confidence=0.7
            )
        
        return CaptchaSolution(
            success=False,
            error="无法识别验证码类型",
            confidence=0.0
        )
    
    def _solve_math_problem(self, text: str) -> Optional[int]:
        """解决数学问题"""
        for pattern in self.math_patterns:
            match = re.search(pattern, text)
            if match:
                numbers = [int(num) for num in match.groups()]
                
                if '+' in text:
                    return sum(numbers)
                elif '-' in text:
                    return numbers[0] - sum(numbers[1:])
                elif '*' in text or '×' in text:
                    result = 1
                    for num in numbers:
                        result *= num
                    return result
                elif '/' in text or '÷' in text:
                    if len(numbers) >= 2:
                        return numbers[0] // numbers[1]
        
        return None
    
    def _solve_simple_question(self, text: str) -> Optional[str]:
        """解决简单问题"""
        questions = {
            "capital of france": "paris",
            "capital of germany": "berlin",
            "color of sky": "blue",
            "2+2": "4",
            "human": "yes",
            "robot": "no",
            "are you a bot": "no",
            "are you human": "yes",
        }
        
        for question, answer in questions.items():
            if question in text:
                return answer
        
        return None

class HumanLikeSolver(BaseCaptchaSolver):
    """人类行为模拟解决器（最终备用方案）"""
    
    def __init__(self):
        super().__init__()
        self.name = "human_like_solver"
        self.supported_types = ["all"]  # 支持所有类型
    
    def solve(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """通过模拟人类行为解决验证码"""
        print(f"👤 使用人类行为模拟...")
        
        # 生成人类行为序列
        behavior_plan = self._generate_human_behavior()
        
        return CaptchaSolution(
            success=True,  # 总是返回成功，但置信度低
            action="human_sequence",
            value=behavior_plan,
            confidence=0.3  # 低置信度
        )
    
    def _generate_human_behavior(self) -> list:
        """生成人类行为序列"""
        behaviors = []
        
        # 随机鼠标移动
        behaviors.append({
            "type": "mouse_move",
            "points": [(100, 200), (300, 150), (250, 300)]
        })
        
        # 随机点击
        import random
        click_count = random.randint(2, 5)
        for i in range(click_count):
            behaviors.append({
                "type": "click",
                "position": (random.randint(50, 450), random.randint(50, 450)),
                "delay": random.uniform(0.5, 2.0)
            })
        
        # 随机滚动
        behaviors.append({
            "type": "scroll",
            "amount": random.randint(100, 500),
            "delay": random.uniform(0.5, 1.5)
        })
        
        return behaviors

class CaptchaResolver:
    """验证码解析器（协调多个解决器）"""
    
    def __init__(self):
        self.solvers = [
            DuckDuckGoCaptchaSolver(),
            TextCaptchaSolver(),
            HumanLikeSolver(),
        ]
        
        # 验证码类型检测模式（优化版，减少误报）
        self.detection_patterns = {
            "duck_select": [
                r"select all squares containing a duck",
                r"选择.*所有.*包含.*鸭子.*方块",
                r"duck.*select.*squares",
                r"select.*duck.*squares",
            ],
            "text_input": [
                r"enter (?:the )?(?:text|code|captcha|verification code)",
                r"type (?:the )?(?:text|code|captcha)",
                r"输入(?:验证码|代码)",
                r"请输入(?:验证码|代码)",
                r"captcha code.*:",
                r"验证码.*:",
                r"verification code.*:",
                r"code.*\d{4,6}",  # 4-6位数字代码
            ],
            "math_problem": [
                r"what is \d+\s*[+\-*/]\s*\d+\s*\?",
                r"solve.*\d+\s*[+\-*/]\s*\d+",
                r"计算.*\d+.*[+\-*/].*\d+",
                r"\d+\s*[+\-*/]\s*\d+\s*=\s*\?",
                r"\d+\s*[+\-*/]\s*\d+\s*enter.*result",
            ],
        }
    
    def detect_captcha_type(self, content: str) -> Optional[CaptchaChallenge]:
        """检测验证码类型"""
        if not content:
            return None
        
        content_lower = content.lower()
        
        for captcha_type, patterns in self.detection_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    print(f"🔍 检测到验证码类型: {captcha_type}")
                    return CaptchaChallenge(
                        type=captcha_type,
                        content=content,
                        metadata={"detected_by": pattern}
                    )
        
        # 如果没有明确匹配，检查是否是明显的验证码上下文
        # 更严格的关键词+上下文判断
        captcha_contexts = [
            # 英文验证码上下文
            (r"please (?:enter|type|solve).*captcha", "unknown"),
            (r"captcha (?:required|needed|verification)", "unknown"),
            (r"robot check.*click", "unknown"),
            (r"are you a robot\?", "unknown"),
            (r"verify.*human", "unknown"),
            # 中文验证码上下文
            (r"请输入验证码", "unknown"),
            (r"验证码.*输入", "unknown"),
            (r"人机验证", "unknown"),
            (r"机器人.*检测", "unknown"),
        ]
        
        for pattern, captcha_type in captcha_contexts:
            if re.search(pattern, content_lower, re.IGNORECASE):
                print(f"⚠️  检测到通用验证码（上下文匹配）")
                return CaptchaChallenge(
                    type=captcha_type,
                    content=content,
                    metadata={"detected_by": pattern}
                )
        
        # 最后尝试：高频关键词+长度限制（避免文章中的偶然出现）
        # 只有当内容较短且包含关键词时才认为是验证码
        if len(content) < 200:  # 验证码通常简短
            strong_keywords = [
                r"captcha", r"验证码", r"robot check", r"人机验证",
                r"我不是机器人", r"i'm not a robot"
            ]
            for keyword in strong_keywords:
                if re.search(keyword, content_lower, re.IGNORECASE):
                    # 进一步检查是否有动作词
                    action_words = ["enter", "type", "click", "select", "输入", "点击", "选择"]
                    has_action = any(word in content_lower for word in action_words)
                    if has_action:
                        print(f"⚠️  检测到通用验证码（关键词+动作）")
                        return CaptchaChallenge(
                            type="unknown",
                            content=content,
                            metadata={"detected_by": "keyword_action"}
                        )
        
        return None
    
    def solve_captcha(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """尝试解决验证码"""
        print(f"🎯 尝试解决 {challenge.type} 验证码...")
        
        # 按优先级尝试解决器
        for solver in self.solvers:
            if solver.can_solve(challenge):
                print(f"  使用解决器: {solver.name}")
                solution = solver.solve(challenge)
                return solution
        
        # 如果没有解决器能处理，使用人类行为模拟
        print(f"  使用备用解决器: human_like_solver")
        return HumanLikeSolver().solve(challenge)
    
    def auto_resolve(self, content: str, page_snapshot=None) -> Tuple[bool, Optional[CaptchaSolution]]:
        """
        自动检测并解决验证码
        
        Args:
            content: 页面内容
            page_snapshot: 页面快照（可选，用于图像验证码）
            
        Returns:
            (是否检测到验证码, 解决方案)
        """
        # 检测验证码
        challenge = self.detect_captcha_type(content)
        if not challenge:
            return False, None
        
        # 如果有页面快照，添加到元数据
        if page_snapshot:
            challenge.metadata["page_snapshot"] = page_snapshot
        
        # 尝试解决
        solution = self.solve_captcha(challenge)
        
        return True, solution

# 全局实例
_global_resolver = None

def get_global_resolver() -> CaptchaResolver:
    """获取全局验证码解析器实例"""
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = CaptchaResolver()
    return _global_resolver

def test_captcha_resolver():
    """测试验证码解析器"""
    print("🧪 测试验证码解析器")
    print("=" * 50)
    
    resolver = get_global_resolver()
    
    # 测试用例
    test_cases = [
        ("Select all squares containing a duck", "duck_select"),
        ("请选择所有包含鸭子的方块", "duck_select"),
        ("Enter the text you see: ABC123", "text_input"),
        ("What is 15 + 27?", "math_problem"),
        ("验证码: 3829", "text_input"),
        ("Please solve: 42 * 3 = ?", "math_problem"),
        ("Are you human? Click here to continue.", "unknown"),
    ]
    
    for content, expected_type in test_cases:
        print(f"\n📄 测试内容: {content[:40]}...")
        challenge = resolver.detect_captcha_type(content)
        
        if challenge:
            print(f"  检测到: {challenge.type} (预期: {expected_type})")
            print(f"  匹配模式: {challenge.metadata.get('detected_by', 'N/A')}")
            
            # 尝试解决
            solution = resolver.solve_captcha(challenge)
            print(f"  解决结果: {'✅ 成功' if solution.success else '❌ 失败'}")
            print(f"  置信度: {solution.confidence}")
            if solution.error:
                print(f"  错误: {solution.error}")
        else:
            print(f"  未检测到验证码 (预期: {expected_type})")
    
    print(f"\n{'='*50}")
    print("✅ 验证码解析器测试完成")

if __name__ == "__main__":
    test_captcha_resolver()