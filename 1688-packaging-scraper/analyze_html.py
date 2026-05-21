"""分析1688搜索页面实际内容 - 判断是否成功加载了搜索结果"""
from pathlib import Path

h = Path(r'C:\Users\admin\Desktop\1688-packaging-scraper\debug_page.html').read_text('utf-8')

# 检查各种可能性
checks = [
    ("登录页面", ["login", "signin", "请登录", "会员登录", "登录阿里"]),
    ("验证码", ["captcha", "验证码", "安全验证", "滑块验证"]),
    ("空搜索结果", ["没有找到相关产品", "找不到相关产品", "抱歉", "未找到"]),
    ("搜索结果", ["search-offer", "offer-item", "offer-title", "data-offer-id"]),
    ("反爬检测", ["访问受限", "访问被拒绝", "禁止访问", "blocked"]),
    ("加载中", ["loading", "正在加载"]),
]

for name, keywords in checks:
    found = [kw for kw in keywords if kw.lower() in h.lower()]
    if found:
        print(f"🔍 {name}: {found}")
    else:
        print(f"✅ 不是{name}")

# HTML标题
import re
title_match = re.search(r'<title>([^<]+)</title>', h)
if title_match:
    print(f"\n📌 页面标题: {title_match.group(1)}")

# 检查是否包含用户信息（判断是否登录）
for check in ["logout", "退出", "我的阿里", "我的1688", "您好"]:
    if check in h:
        count = h.count(check)
        print(f"👤 已登录标识 '{check}' 出现 {count} 次")

# 查看页面主体可见文本（前1000字符）
body_match = re.search(r'<body[^>]*>(.*?)</body>', h, re.DOTALL)
if body_match:
    body = body_match.group(1)
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', body)
    text = re.sub(r'\s+', ' ', text).strip()
    print(f"\n📄 页面文本 (前500字):")
    print(text[:500])

# 检查是否被重定向到别的页面
offer_count = len(re.findall(r'offer', h))
detail_count = len(re.findall(r'detail\.1688\.com', h))
print(f"\n🔗 URL中的offer链接数量: {offer_count}")
print(f"🔗 detail.1688.com 链接数量: {detail_count}")
