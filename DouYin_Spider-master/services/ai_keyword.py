"""
AI关键词提取与跨赛道推荐服务
基于品牌画像调用豆包大模型（火山方舟Ark API）生成搜索关键词和跨赛道建议
"""

import json
import os
import re

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ---- 配置 ----
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
AI_MODEL = os.getenv("AI_MODEL", "doubao-seed-2-0-pro-260215")


def _call_ai(prompt: str) -> str:
    """
    调用豆包API（Ark API /responses 端点），返回AI响应文本。

    使用 responses 端点（与 script_generator 一致），适配推理模型：
    响应 output 数组包含 reasoning 与 message 两类，需遍历提取最终文本。
    """
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
    }

    url = AI_API_URL.rstrip("/") + "/responses"
    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    # 遍历 output，优先取 message 类型的 content 文本
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            text = c.get("text", "")
            if text:
                return text

    # 兜底：reasoning 的 summary 文本
    for item in data.get("output", []) or []:
        for s in item.get("summary", []) or []:
            text = s.get("text", "")
            if text:
                logger.warning("仅获取到reasoning文本，非最终回答")
                return text

    # 最终兜底：返回原始数据字符串，由调用方 _parse_json_response 尝试解析
    logger.warning("AI响应格式异常: {}".format(str(data)[:500]))
    return str(data)


def _parse_json_response(text: str) -> dict:
    """从AI返回文本中提取JSON，容错处理。"""
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 返回空字典，由调用方处理
    return {}


def _build_brand_text(brand: dict) -> str:
    """将品牌画像字典转换为可读文本。"""
    parts = []
    if brand.get("name"):
        parts.append(f"品牌/账号名称：{brand['name']}")
    if brand.get("category"):
        parts.append(f"品类赛道：{brand['category']}")
    if brand.get("product_desc"):
        parts.append(f"产品/内容描述：{brand['product_desc']}")
    if brand.get("target_audience"):
        parts.append(f"目标人群：{brand['target_audience']}")
    if brand.get("selling_points"):
        parts.append(f"核心卖点/特色：{brand['selling_points']}")
    return "\n".join(parts) if parts else json.dumps(brand, ensure_ascii=False)


# ---- 默认关键词生成（API不可用时的降级方案） ----

def _default_keywords(brand: dict) -> dict:
    """基于品牌字段简单拼接默认关键词。"""
    name = brand.get("name", "")
    category = brand.get("category", "")
    product_desc = brand.get("product_desc", "")
    target_audience = brand.get("target_audience", "")
    selling_points = brand.get("selling_points", "")

    category_keywords = []
    if category:
        category_keywords.append(category)
        category_keywords.append(f"{category}推荐")
        category_keywords.append(f"{category}排行")
    if name:
        category_keywords.append(f"{name}同款")
    if product_desc:
        category_keywords.append(product_desc)

    scene_keywords = []
    if "宠物" in category or "狗" in category or "猫" in category:
        scene_keywords.extend(["宠物日常", "遛狗", "宠物出行", "宠物聚会"])
    elif "穿搭" in category or "服装" in category:
        scene_keywords.extend(["日常穿搭", "出行穿搭", "拍照穿搭"])
    else:
        scene_keywords.extend(["日常使用", "推荐好物"])

    audience_keywords = []
    if target_audience:
        audience_keywords.append(target_audience)
    audience_keywords.extend(["热门推荐", "大家都在搜"])

    content_keywords = ["测评", "推荐", "教程", "开箱"]

    return {
        "category_keywords": category_keywords,
        "scene_keywords": scene_keywords,
        "audience_keywords": audience_keywords,
        "content_keywords": content_keywords,
    }


def _default_cross_categories(brand: dict) -> dict:
    """默认跨赛道推荐（无AI时返回空列表）。"""
    return {"categories": []}


# ---- 公开 API ----

def extract_keywords(brand: dict) -> dict:
    """
    基于品牌画像调用AI提取搜索关键词。

    参数:
        brand: 品牌画像字典，需包含:
            - name (str): 品牌/账号名称
            - category (str): 品类赛道
            - product_desc (str): 产品/内容描述
            - target_audience (str): 目标人群
            - selling_points (str): 核心卖点/特色

    返回:
        dict: {
            "category_keywords": [...],   # 品类相关搜索词
            "scene_keywords": [...],      # 场景相关搜索词
            "audience_keywords": [...],   # 人群相关搜索词
            "content_keywords": [...]     # 内容形式相关搜索词
        }
    """
    brand_text = _build_brand_text(brand)

    prompt = f"""你是一个专业的抖音搜索关键词策略专家。请根据以下品牌/账号画像，为该品牌在抖音平台上生成搜索关键词策略。

{brand_text}

请输出严格的JSON格式（不要包含其他任何文字），结构如下：
{{
    "category_keywords": ["品类搜索词1", "品类搜索词2", ...],
    "scene_keywords": ["场景搜索词1", "场景搜索词2", ...],
    "audience_keywords": ["人群搜索词1", "人群搜索词2", ...],
    "content_keywords": ["内容形式搜索词1", "内容形式搜索词2", ...]
}}

要求：
1. category_keywords: 用户会搜索的品类/产品词，如"宠物衣服"、"狗狗穿搭"、"猫咪衣服"。5-10个。
2. scene_keywords: 使用场景相关，如"遛狗穿搭"、"宠物生日派对"、"春节宠物装"。3-6个。
3. audience_keywords: 目标人群会搜的词，如"铲屎官必备"、"养狗新手推荐"。3-6个。
4. content_keywords: 内容形式词，如"教程"、"测评"、"穿搭"、"vlog"、"开箱"。3-6个。
5. 每个关键词应简洁、符合抖音用户搜索习惯、有实际搜索量潜力。
6. 只输出JSON，不要任何额外解释。"""

    try:
        response_text = _call_ai(prompt)
        result = _parse_json_response(response_text)
        if result and all(
            k in result for k in ["category_keywords", "scene_keywords", "audience_keywords", "content_keywords"]
        ):
            return result
        else:
            raise ValueError("AI返回的JSON缺少必要字段")
    except Exception as e:
        logger.error(f"AI关键词提取失败: {type(e).__name__}: {e}")
        return _default_keywords(brand)


def recommend_cross_categories(brand: dict) -> dict:
    """
    AI推荐可借鉴的跨赛道品类。

    参数:
        brand: 品牌画像字典（同 extract_keywords）

    返回:
        dict: {
            "categories": [
                {"name": "品类名", "reason": "借鉴理由", "search_keywords": ["搜索词1", ...]},
                ...
            ]
        }
    """
    brand_text = _build_brand_text(brand)

    prompt = f"""你是一个专业的抖音内容策略专家。请根据以下品牌/账号画像，分析并推荐该品牌可以借鉴的"跨赛道"品类。

{brand_text}

请输出严格的JSON格式（不要包含其他任何文字），结构如下：
{{
    "categories": [
        {{
            "name": "可借鉴的品类名称",
            "reason": "为什么值得借鉴（具体说明该品类的内容形式、选题策略、运营模式等方面值得学习的地方）",
            "search_keywords": ["在该品类下可以搜索的关键词1", "关键词2", ...]
        }}
    ]
}}

要求：
1. 推荐3-5个跨赛道品类。
2. 每个品类应来自不同的领域（如母婴、美食、美妆、家居、教育等），与本品牌的赛道有明显差异但有可借鉴之处。
3. reason要具体，不能泛泛而谈，说明具体可借鉴的切入点。
4. search_keywords 3-5个，是在抖音上搜索该品类相关内容会用到的词。
5. 只输出JSON，不要任何额外解释。"""

    try:
        response_text = _call_ai(prompt)
        result = _parse_json_response(response_text)
        if result and "categories" in result:
            return result
        else:
            raise ValueError("AI返回的JSON缺少必要字段")
    except Exception as e:
        logger.error(f"跨赛道AI推荐失败: {type(e).__name__}: {e}")
        return _default_cross_categories(brand)


# ---- 自测 ----
if __name__ == "__main__":
    # 测试品牌画像
    test_brand = {
        "name": "爪裁舍宠物服装定制",
        "category": "宠物服装",
        "product_desc": "手工定制宠物服装，主打高品质、个性化设计，提供打板教程",
        "target_audience": "养宠物的年轻女性，注重宠物生活品质，喜欢DIY和个性化产品",
        "selling_points": "零基础打板教程、手工定制、高端面料、独一无二的设计",
    }

    print("=" * 60)
    print(">>> 关键词提取测试")
    print("=" * 60)
    keywords = extract_keywords(test_brand)
    print(json.dumps(keywords, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print(">>> 跨赛道推荐测试")
    print("=" * 60)
    cross = recommend_cross_categories(test_brand)
    print(json.dumps(cross, ensure_ascii=False, indent=2))
