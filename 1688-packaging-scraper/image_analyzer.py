"""
1688 包装图片分析模块
使用 OpenCV + PIL + scikit-image 对包装类产品图片进行：
- 主色调分析
- 形状/轮廓检测
- 材质纹理分析
- 视觉风格归类
- 爆款特征总结
"""
import re
import json
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

try:
    import cv2
    from PIL import Image
    from skimage import feature, color, morphology, measure
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

import config


# ──────────────────────────────────────────────
#  数据模型
# ──────────────────────────────────────────────

@dataclass
class ColorInfo:
    """颜色分析结果"""
    dominant_colors: List[Dict] = field(default_factory=list)    # [{"rgb": [r,g,b], "hex": "#xxxxxx", "name": "红色", "ratio": 0.5}, ...]
    color_palette_type: str = ""     # 暖色调/冷色调/中性色调/多彩
    brightness: str = ""             # 明亮/中等/暗沉
    saturation: str = ""             # 鲜艳/柔和/灰暗
    has_gold: bool = False           # 是否含金色
    has_white: bool = False          # 是否大面积白色
    color_count: int = 0             # 主要颜色数量

    def to_dict(self):
        return asdict(self)


@dataclass
class ShapeInfo:
    """形状分析结果"""
    shape_type: str = ""             # 方盒型/圆筒型/袋型/异型/不规则
    aspect_ratio: float = 0.0        # 宽高比
    contour_count: int = 0           # 轮廓数量
    has_rounded_corners: bool = False
    symmetry: str = ""               # 对称/不对称
    complexity: str = ""             # 简约/中等/复杂

    def to_dict(self):
        return asdict(self)


@dataclass
class MaterialInfo:
    """材质分析结果"""
    material_type: str = ""          # 纸质/塑料/金属/玻璃/布料/综合
    surface_texture: str = ""        # 光滑/磨砂/纹理/粗糙
    gloss_level: str = ""            # 高光/亚光/哑光
    is_luxury: bool = False          # 是否高端质感
    has_foil: bool = False           # 是否有烫金/烫银
    confidence: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class ImageAnalysisResult:
    """完整图片分析结果"""
    file_path: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    file_size_kb: float = 0.0

    # 三大分析维度
    color: ColorInfo = field(default_factory=ColorInfo)
    shape: ShapeInfo = field(default_factory=ShapeInfo)
    material: MaterialInfo = field(default_factory=MaterialInfo)

    # 综合归类
    visual_category: str = ""        # 简约白盒/高端礼盒/彩色包装/极简设计/自然风格/奢华风格/科技风格
    style_tags: List[str] = field(default_factory=list)
    summary: str = ""

    # 爆款特征
    trending_features: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "file_size_kb": round(self.file_size_kb, 1),
            "color": self.color.to_dict(),
            "shape": self.shape.to_dict(),
            "material": self.material.to_dict(),
            "visual_category": self.visual_category,
            "style_tags": self.style_tags,
            "summary": self.summary,
            "trending_features": self.trending_features,
        }


# ──────────────────────────────────────────────
#  颜色名称映射（中文）
# ──────────────────────────────────────────────

COLOR_NAMES_CN = {
    (255, 0, 0): "红色", (200, 50, 50): "酒红", (255, 100, 100): "粉色",
    (255, 165, 0): "橙色", (255, 200, 0): "金色", (255, 255, 0): "黄色",
    (0, 128, 0): "绿色", (0, 200, 0): "翠绿", (0, 255, 0): "亮绿",
    (0, 0, 255): "蓝色", (0, 100, 200): "深蓝", (100, 150, 255): "天蓝",
    (128, 0, 128): "紫色", (200, 0, 200): "紫红", (255, 0, 255): "品红",
    (255, 255, 255): "白色", (240, 240, 240): "米白", (200, 200, 200): "灰色",
    (128, 128, 128): "中灰", (0, 0, 0): "黑色", (50, 50, 50): "深灰",
    (210, 180, 140): "米色", (139, 90, 43): "棕色", (160, 120, 90): "咖啡色",
    (192, 192, 192): "银色", (255, 215, 0): "金色", (0, 128, 128): "青色",
    (72, 61, 139): "深紫", (255, 127, 80): "珊瑚色", (220, 20, 60): "胭脂红",
}

# 扩展的高端色
LUXURY_COLORS = [
    (255, 215, 0),   # 金色
    (192, 192, 192), # 银色
    (139, 0, 0),     # 深红
    (0, 0, 128),     # 深蓝
    (128, 0, 128),   # 紫色
    (50, 50, 50),    # 深灰（高端黑）
    (25, 25, 25),    # 纯黑
    (210, 180, 140), # 米色（高端）
]


def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(c1, c2):
    """计算两个颜色之间的欧几里得距离"""
    return np.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def find_closest_color_name(rgb):
    """找到最接近的中文颜色名"""
    min_dist = float("inf")
    closest_name = "未知"
    for c, name in COLOR_NAMES_CN.items():
        dist = color_distance(rgb, c)
        if dist < min_dist:
            min_dist = dist
            closest_name = name
    return closest_name


def get_color_temperature(rgb):
    """判断色温：暖/冷/中性"""
    r, g, b = rgb
    if r > g + 20 and r > b + 20:
        return "暖色调"
    if b > r + 20 and b > g + 10:
        return "冷色调"
    if abs(r - g) < 30 and abs(g - b) < 30 and abs(r - b) < 30:
        return "中性色调"
    return "暖色调" if r > b else "冷色调"


# ──────────────────────────────────────────────
#  图片加载
# ──────────────────────────────────────────────

def load_image(path: str) -> Optional[np.ndarray]:
    """加载图片为OpenCV格式"""
    if not HAS_OPENCV:
        return None
    img = cv2.imread(path)
    if img is None:
        return None
    return img


def load_image_pil(path: str) -> Optional[Image.Image]:
    """加载图片为PIL格式"""
    try:
        return Image.open(path)
    except:
        return None


# ──────────────────────────────────────────────
#  颜色分析
# ──────────────────────────────────────────────

def analyze_colors(img: np.ndarray) -> ColorInfo:
    """分析图片的主色调"""
    result = ColorInfo()

    # 1. 缩小尺寸加速处理
    h, w = img.shape[:2]
    scale = min(200 / w, 200 / h)
    small = cv2.resize(img, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # 2. 转为RGB
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    pixels = rgb.reshape(-1, 3)

    # 3. K-means聚类获取主色调 (k=5)
    k = 5
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(
        pixels.astype(np.float32), k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    # 4. 统计各颜色比例
    label_counts = Counter(labels.flatten())
    total_pixels = len(labels)

    dominant_colors = []
    for label_idx in range(k):
        ratio = label_counts[label_idx] / total_pixels
        center = centers[label_idx].astype(int).tolist()
        r, g, b = center
        name = find_closest_color_name((r, g, b))
        hex_color = rgb_to_hex(r, g, b)

        dominant_colors.append({
            "rgb": center,
            "hex": hex_color,
            "name": name,
            "ratio": round(ratio, 3),
        })

    # 按比例排序
    dominant_colors.sort(key=lambda x: -x["ratio"])
    result.dominant_colors = dominant_colors[:5]

    # 5. 判断色调类型
    top_colors = [c["rgb"] for c in dominant_colors[:3]]
    temperatures = [get_color_temperature(c) for c in top_colors]
    warm_count = temperatures.count("暖色调")
    cold_count = temperatures.count("冷色调")

    if warm_count >= 2:
        result.color_palette_type = "暖色调"
    elif cold_count >= 2:
        result.color_palette_type = "冷色调"
    else:
        # 看是否有大面积白色/灰色/黑色
        neutral = sum(1 for c in top_colors if get_color_temperature(c) == "中性色调")
        if neutral >= 2:
            result.color_palette_type = "中性色调"
        else:
            result.color_palette_type = "多彩"

    # 6. 亮度分析
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    avg_brightness = np.mean(gray)
    if avg_brightness > 200:
        result.brightness = "明亮"
    elif avg_brightness > 120:
        result.brightness = "中等"
    else:
        result.brightness = "暗沉"

    # 7. 饱和度分析
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    avg_saturation = np.mean(hsv[:, :, 1])
    if avg_saturation > 100:
        result.saturation = "鲜艳"
    elif avg_saturation > 40:
        result.saturation = "柔和"
    else:
        result.saturation = "灰暗"

    # 8. 特殊颜色检测
    for color_info in dominant_colors:
        name = color_info["name"]
        if "金" in name or "银" in name:
            if color_info["ratio"] > 0.05:
                result.has_gold = True
        if "白" in name and color_info["ratio"] > 0.3:
            result.has_white = True

    # 9. 颜色数量
    significant_colors = [c for c in dominant_colors if c["ratio"] > 0.08]
    result.color_count = len(significant_colors)

    return result


# ──────────────────────────────────────────────
#  形状分析
# ──────────────────────────────────────────────

def analyze_shape(img: np.ndarray) -> ShapeInfo:
    """分析图片中的形状特征"""
    result = ShapeInfo()

    h, w = img.shape[:2]
    result.aspect_ratio = round(w / h, 2) if h > 0 else 1.0

    # 1. 边缘检测 + 轮廓查找
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 自适应阈值
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)

    # 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result.contour_count = len(contours)

    # 2. 检测主要轮廓形状
    if contours:
        # 找到最大的几个轮廓
        sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)
        main_contour = sorted_contours[0]

        # 轮廓近似
        peri = cv2.arcLength(main_contour, True)
        approx = cv2.approxPolyDP(main_contour, 0.02 * peri, True)
        num_vertices = len(approx)

        # 判断主形状
        area = cv2.contourArea(main_contour)
        if area < 100:  # 太小忽略
            result.shape_type = "不规则"
        elif num_vertices >= 8:
            result.shape_type = "圆润/异型"
        elif num_vertices >= 5:
            result.shape_type = "多边异型"
        elif num_vertices == 4 or num_vertices == 3:
            # 进一步判断是正方还是长方
            x, y, bw, bh = cv2.boundingRect(main_contour)
            rect_ratio = bw / bh if bh > 0 else 1
            if 0.8 <= rect_ratio <= 1.2:
                result.shape_type = "方盒型"
            else:
                result.shape_type = "长方型"
        else:
            # 圆形度检测
            if area > 0:
                circularity = 4 * np.pi * area / (peri * peri)
                if circularity > 0.7:
                    result.shape_type = "圆筒型"
                else:
                    result.shape_type = "不规则"

        # 3. 圆角检测（检查轮廓是否有弧边）
        # 简单方法：比较凸包面积和原始轮廓面积
        hull = cv2.convexHull(main_contour)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = area / hull_area
            result.has_rounded_corners = solidity < 0.95 and solidity > 0.8
        else:
            result.has_rounded_corners = False

        # 4. 对称性检测
        # 左右翻转对比
        if w > 20:
            left_half = gray[:, :w // 2]
            right_half = gray[:, w // 2:]
            right_flipped = cv2.flip(right_half, 1)

            # 调整为相同大小
            min_w = min(left_half.shape[1], right_flipped.shape[1])
            left_half = left_half[:, :min_w]
            right_flipped = right_flipped[:, :min_w]

            if left_half.size > 0 and right_flipped.size > 0:
                similarity = np.mean(np.abs(left_half.astype(float) - right_flipped.astype(float)))
                if similarity < 30:
                    result.symmetry = "对称"
                else:
                    result.symmetry = "不对称"
            else:
                result.symmetry = "未知"
    else:
        result.shape_type = "未知"

    # 5. 复杂度分析
    edge_density = np.mean(edges) / 255.0 if edges.size > 0 else 0
    if edge_density < 0.05:
        result.complexity = "简约"
    elif edge_density < 0.15:
        result.complexity = "中等"
    else:
        result.complexity = "复杂"

    return result


# ──────────────────────────────────────────────
#  材质分析
# ──────────────────────────────────────────────

def analyze_material(img: np.ndarray) -> MaterialInfo:
    """分析图片中的材质特征"""
    result = MaterialInfo()

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 纹理分析 - 使用GLCM
    # 简化：通过局部方差分析纹理粗糙度
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    laplacian = cv2.Laplacian(blurred, cv2.CV_64F)
    texture_variance = np.var(laplacian)

    # 纹理分类
    if texture_variance < 50:
        result.surface_texture = "光滑"
    elif texture_variance < 200:
        result.surface_texture = "磨砂"
    elif texture_variance < 500:
        result.surface_texture = "纹理"
    else:
        result.surface_texture = "粗糙"

    # 2. 光泽度分析（检测高光区域）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # 高光 = 低饱和度 + 高亮度
    highlight_mask = (hsv[:, :, 1] < 30) & (hsv[:, :, 2] > 200)
    highlight_ratio = np.sum(highlight_mask) / (h * w) if h * w > 0 else 0

    if highlight_ratio > 0.15:
        result.gloss_level = "高光"
    elif highlight_ratio > 0.05:
        result.gloss_level = "亚光"
    else:
        result.gloss_level = "哑光"

    # 3. 烫金/烫银检测
    # 检测金色区域（HSV范围）
    lower_gold = np.array([15, 50, 100])
    upper_gold = np.array([35, 255, 255])
    gold_mask = cv2.inRange(hsv, lower_gold, upper_gold)
    gold_ratio = np.sum(gold_mask > 0) / (h * w) if h * w > 0 else 0

    # 检测银色/高亮区域
    lower_silver = np.array([0, 0, 180])
    upper_silver = np.array([180, 30, 255])
    silver_mask = cv2.inRange(hsv, lower_silver, upper_silver)
    silver_ratio = np.sum(silver_mask > 0) / (h * w) if h * w > 0 else 0

    result.has_foil = (gold_ratio > 0.03 or silver_ratio > 0.05)

    # 4. 材质识别
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 判断纸质：纹理中等、亚光、自然色系
    is_paper_like = (texture_variance > 30 and texture_variance < 300
                     and result.gloss_level in ("哑光", "亚光")
                     and not result.has_foil)

    # 判断塑料：光滑、可能高光
    is_plastic_like = (texture_variance < 80 and result.gloss_level == "高光"
                       and highlight_ratio > 0.05)

    # 判断金属：高对比度、高光明显
    is_metal_like = (result.has_foil or (highlight_ratio > 0.2 and texture_variance > 100))

    # 判断布料：纹理粗糙、哑光
    is_fabric_like = (texture_variance > 300 and result.gloss_level == "哑光"
                      and not result.has_foil)

    # 综合判断
    material_scores = {
        "纸质": is_paper_like,
        "塑料": is_plastic_like,
        "金属": is_metal_like,
        "布料": is_fabric_like,
    }

    # 如果有烫金，一般是高端包装，材质可能是综合
    if result.has_foil:
        result.material_type = "综合（烫金工艺）"
        result.is_luxury = True
    elif is_paper_like:
        result.material_type = "纸质"
    elif is_plastic_like:
        result.material_type = "塑料"
    elif is_metal_like:
        result.material_type = "金属质感"
    elif is_fabric_like:
        result.material_type = "布料"
    else:
        result.material_type = "综合"

    # 5. 高端感判断
    luxury_score = 0
    if result.has_foil:
        luxury_score += 3
    if result.gloss_level == "高光":
        luxury_score += 1
    if result.surface_texture == "光滑":
        luxury_score += 0.5
    if result.material_type == "综合（烫金工艺）":
        luxury_score += 2

    result.is_luxury = luxury_score >= 3
    result.confidence = min(1.0, luxury_score / 6)

    return result


# ──────────────────────────────────────────────
#  综合视觉归类
# ──────────────────────────────────────────────

def classify_visual_style(color: ColorInfo, shape: ShapeInfo, material: MaterialInfo) -> Tuple[str, List[str]]:
    """综合三个维度进行视觉风格归类"""
    tags = []

    # 1. 主风格判定
    is_simple = (color.color_count <= 2 and
                 color.saturation == "灰暗" and
                 shape.complexity == "简约")
    is_luxury = material.is_luxury
    is_colorful = (color.color_palette_type == "多彩" or
                   (color.color_count >= 3 and color.saturation == "鲜艳"))
    is_natural = ("米" in [c["name"] for c in color.dominant_colors[:2]] or
                  "棕" in [c["name"] for c in color.dominant_colors[:2]] or
                  "绿" in [c["name"] for c in color.dominant_colors[:2]])
    is_bright = (color.brightness == "明亮" and color.saturation == "鲜艳")
    is_dark_luxury = (color.brightness == "暗沉" and
                      any(c["name"] in ["黑色", "深蓝", "深紫", "深灰"]
                          for c in color.dominant_colors[:2]) and
                      material.has_foil)
    is_minimalist = (color.has_white and color.color_count <= 2 and shape.complexity == "简约")

    # 2. 标签
    if material.has_foil:
        tags.append("烫金工艺")
    if color.has_gold:
        tags.append("金色元素")
    if color.has_white and color.dominant_colors[0]["name"] == "白色":
        tags.append("白底设计")
    if color.color_count <= 2:
        tags.append("双色搭配")
    elif color.color_count >= 4:
        tags.append("多色设计")
    if shape.has_rounded_corners:
        tags.append("圆角设计")
    if shape.complexity == "复杂":
        tags.append("精细图案")
    if material.gloss_level == "高光":
        tags.append("高光质感")
    if material.surface_texture == "磨砂":
        tags.append("磨砂质感")
    if color.brightness == "明亮":
        tags.append("清新明亮")
    if color.brightness == "暗沉":
        tags.append("深邃风格")
    if color.saturation == "鲜艳":
        tags.append("色彩鲜艳")
    if shape.symmetry == "对称":
        tags.append("左右对称")

    # 3. 最终分类
    if is_dark_luxury:
        category = "深色奢华风格"
        tags.append("高端深色")
    elif is_luxury and is_colorful:
        category = "奢华多彩风格"
    elif is_luxury:
        category = "高端奢华风格"
    elif is_minimalist:
        category = "简约白盒风格"
        tags.append("极简设计")
    elif is_simple:
        category = "简约风格"
    elif is_natural and not is_colorful:
        category = "自然环保风格"
        tags.append("环保自然")
    elif is_bright:
        category = "明亮清新风格"
    elif is_colorful:
        category = "多彩设计风格"
    else:
        category = "经典风格"

    return category, list(set(tags))


def generate_analysis_summary(category: str, tags: List[str],
                               color: ColorInfo, material: MaterialInfo) -> str:
    """生成分析摘要"""
    top_colors = [c["name"] for c in color.dominant_colors[:3]]
    color_desc = "、".join(top_colors) if top_colors else "未知"

    summary_parts = []
    summary_parts.append(f"主色调：{color_desc}")
    summary_parts.append(f"风格：{category}")
    summary_parts.append(f"材质：{material.material_type}")
    summary_parts.append(f"表面：{material.surface_texture}、{material.gloss_level}")

    if tags:
        summary_parts.append("特点：" + "、".join(tags[:4]))

    return " | ".join(summary_parts)


def generate_trending_features(category: str, tags: List[str],
                                color: ColorInfo, material: MaterialInfo) -> List[str]:
    """生成爆款特征总结"""
    features = []

    # 基于分析结果生成营销角度的特征描述
    if material.has_foil:
        features.append("烫金工艺提升档次感")
    if "简约" in category or "白盒" in category:
        features.append("简约设计符合现代审美趋势")
    if "奢华" in category or "高端" in category:
        features.append("高端质感吸引礼品市场")
    if "自然" in category or "环保" in category:
        features.append("环保自然风契合ESG消费趋势")
    if color.saturation == "鲜艳":
        features.append("鲜艳配色提升货架视觉冲击力")
    if color.brightness == "明亮":
        features.append("明亮色调增加产品吸引力")
    if "多色" in category or "多彩" in category:
        features.append("多色设计满足个性化需求")
    if color.has_white:
        features.append("白色基底凸显洁净品质感")
    if "经典" in category:
        features.append("经典设计安全稳妥适配广泛客群")
    if material.gloss_level == "哑光":
        features.append("哑光工艺呈现高级质感")
    if shape.symmetry == "对称":
        features.append("对称设计给人以规整专业印象")

    # 去重
    seen = set()
    unique_features = []
    for f in features:
        if f not in seen:
            seen.add(f)
            unique_features.append(f)

    return unique_features[:5]  # 最多5条


# ──────────────────────────────────────────────
#  批量分析
# ──────────────────────────────────────────────

def analyze_single_image(image_path: str) -> Optional[ImageAnalysisResult]:
    """分析单张图片"""
    if not HAS_OPENCV:
        return None

    img = load_image(image_path)
    if img is None:
        return None

    result = ImageAnalysisResult()
    result.file_path = image_path
    result.filename = Path(image_path).name

    h, w = img.shape[:2]
    result.width = w
    result.height = h
    result.file_size_kb = Path(image_path).stat().st_size / 1024

    # 三大分析
    result.color = analyze_colors(img)
    result.shape = analyze_shape(img)
    result.material = analyze_material(img)

    # 综合
    category, tags = classify_visual_style(result.color, result.shape, result.material)
    result.visual_category = category
    result.style_tags = tags
    result.summary = generate_analysis_summary(category, tags, result.color, result.material)
    result.trending_features = generate_trending_features(category, tags, result.color, result.material)

    return result


def analyze_all_images(products: List[dict]) -> List[dict]:
    """
    对所有产品图片进行分析
    返回带分析结果的产品列表
    """
    print(f"\n{'='*50}")
    print(f"  🎨 正在进行图片视觉分析...")
    print(f"{'='*50}")

    analyzed_count = 0
    total_products = len(products)

    for idx, product in enumerate(products):
        img_local = product.get("main_image_local", "")
        if not img_local or not Path(img_local).exists():
            product["image_analysis"] = None
            continue

        analysis = analyze_single_image(img_local)
        if analysis:
            product["image_analysis"] = analysis.to_dict()
            analyzed_count += 1
            if idx % 5 == 0:
                print(f"  📸 已分析 {idx+1}/{total_products}...")
        else:
            product["image_analysis"] = None

    print(f"  ✅ 图片分析完成！成功分析 {analyzed_count}/{total_products} 张图片")

    return products


# ──────────────────────────────────────────────
#  统计汇总
# ──────────────────────────────────────────────

def summarize_analysis(products: List[dict]) -> dict:
    """
    对所有产品的分析结果进行汇总统计
    """
    categories_counter = Counter()
    tags_counter = Counter()
    color_counter = Counter()
    material_counter = Counter()
    trending_counter = Counter()
    shape_counter = Counter()

    analyzed = 0
    for p in products:
        analysis = p.get("image_analysis")
        if not analysis:
            continue
        analyzed += 1

        categories_counter[analysis.get("visual_category", "未知")] += 1

        for tag in analysis.get("style_tags", []):
            tags_counter[tag] += 1

        color_info = analysis.get("color", {})
        for c in color_info.get("dominant_colors", []):
            color_counter[c.get("name", "未知")] += c.get("ratio", 0)

        material_info = analysis.get("material", {})
        material_counter[material_info.get("material_type", "未知")] += 1

        shape_info = analysis.get("shape", {})
        shape_counter[shape_info.get("shape_type", "未知")] += 1

        for feat in analysis.get("trending_features", []):
            trending_counter[feat] += 1

    # 颜色比例归一化
    total_ratio = sum(color_counter.values())
    if total_ratio > 0:
        color_summary = {k: round(v / total_ratio * 100, 1) for k, v in color_counter.most_common(10)}
    else:
        color_summary = {}

    # 趋势特征百分比
    total_with_analysis = max(analyzed, 1)

    return {
        "total_analyzed": analyzed,
        "total_products": len(products),
        "analysis_rate": f"{analyzed}/{len(products)}",
        "visual_categories": dict(categories_counter.most_common()),
        "style_tags_rank": dict(tags_counter.most_common(15)),
        "color_distribution": color_summary,
        "material_distribution": dict(material_counter.most_common()),
        "shape_distribution": dict(shape_counter.most_common()),
        "trending_features": dict(trending_counter.most_common(10)),
    }
