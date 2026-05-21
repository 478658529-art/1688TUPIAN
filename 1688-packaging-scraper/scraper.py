"""
1688 包装厂家信息采集模块
修复：等待搜索结果加载+使用正确CSS选择器
"""
import re
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urljoin

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config


def sanitize_filename(text: str, max_len: int = 60) -> str:
    text = re.sub(r'[\\/:*?"<>|]', '_', text)
    text = re.sub(r'\s+', '_', text)
    return text[:max_len]


def download_image(url: str, save_dir: Path, product_id: str, index: int = 0) -> str:
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        ext = ".jpg"
        url_match = re.search(r'\.(jpg|jpeg|png|gif|webp)(?:\?|$)', url.lower())
        if url_match:
            ext = f".{url_match.group(1)}"
        filename = f"{product_id}_{index}{ext}"
        filepath = save_dir / filename
        if filepath.exists():
            return str(filepath)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.1688.com/",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            filepath.write_bytes(resp.content)
            return str(filepath)
        return ""
    except Exception as e:
        print(f"    ⚠️ 图片下载失败：{e}")
        return ""


def extract_product_id(url: str) -> str:
    match = re.search(r'/offer/(\d+)\.html', url)
    if match:
        return match.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:12]


class ProductInfo:
    def __init__(self):
        self.id = ""
        self.title = ""
        self.price = ""
        self.shop_name = ""
        self.shop_url = ""
        self.url = ""
        self.source_keyword = ""
        self.main_image_url = ""
        self.main_image_local = ""
        self.extra_images = []
        self.extra_images_local = []
        self.detail_text = ""
        self.specs = {}
        self.category = ""
        self.sales_info = ""
        self.scrape_time = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "price": self.price,
            "shop_name": self.shop_name,
            "shop_url": self.shop_url,
            "url": self.url,
            "source_keyword": self.source_keyword,
            "main_image_url": self.main_image_url,
            "main_image_local": self.main_image_local,
            "extra_images": self.extra_images,
            "extra_images_local": self.extra_images_local,
            "detail_text": (self.detail_text or "")[:500],
            "specs": self.specs,
            "category": self.category,
            "sales_info": self.sales_info,
            "scrape_time": self.scrape_time,
        }


def auto_categorize(title: str, detail: str) -> str:
    text = (title + " " + detail)
    categories = {
        "纸箱/瓦楞箱": ["纸箱", "瓦楞", "纸盒", "快递箱", "包装箱", "飞机盒", "彩箱"],
        "礼品盒/彩盒": ["礼品盒", "礼盒", "彩盒", "首饰盒", "化妆品盒", "包装盒", "天地盖"],
        "食品包装袋": ["食品袋", "食品包装", "零食袋", "自立袋", "拉链袋", "真空袋", "茶叶袋"],
        "快递袋/物流袋": ["快递袋", "物流袋", "气泡袋", "快递包装", "珠光膜袋"],
        "手提袋/纸袋": ["手提袋", "纸袋", "手袋", "礼品袋", "购物袋", "环保袋"],
        "塑料包装": ["塑料袋", "pe袋", "opp袋", "复合袋", "塑料膜", "缠绕膜", "收缩膜"],
        "标签/不干胶": ["不干胶", "标签", "贴纸", "条形码", "吊牌"],
        "包装辅料": ["胶带", "打包带", "缠绕膜", "气泡膜", "珍珠棉", "护角", "干燥剂"],
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "其他包装"


def scrape_search_results(page, keyword: str, max_products: int) -> list:
    """
    在1688搜索关键词，获取搜索结果列表
    修复版：等待搜索页面真正加载完成，使用正确的CSS选择器
    """
    print(f"\n🔍 正在搜索：{keyword}")
    search_url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}&n=y"

    # ⭐ 关键修复：使用 wait_until='networkidle' 确保网络请求全部完成
    page.goto(search_url, timeout=config.PAGE_LOAD_TIMEOUT, wait_until='networkidle')

    # ⭐ 等待产品真正出现在页面中（等待detail链接出现）
    print("  ⏳ 等待动态产品数据加载...")
    try:
        # 使用JS轮询等待产品链接出现（最长等25秒）
        loaded = page.wait_for_function("""
            () => {
                // 兼容各种URL格式：绝对路径、协议相对路径
                const links = document.querySelectorAll(
                    'a[href*="detail.1688.com/offer/"], ' +
                    'a[href*="//detail.1688.com/offer/"]'
                );
                // 必须有标题的链接才算有效产品
                let validCount = 0;
                for (const a of links) {
                    const t = (a.getAttribute('title') || a.innerText || '').trim();
                    if (t.length >= 5) validCount++;
                    if (validCount >= 3) return true;
                }
                return false;
            }
        """, timeout=25000)
        print("  ✅ 产品数据已加载")
    except:
        print("  ⚠️ 产品加载超时，继续尝试...")

    # 额外等待确保渲染完成
    time.sleep(2)

    # 滚动页面加载更多产品
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(config.SCROLL_PAUSE_TIME)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)

    products = []
    seen_urls = set()

    # ⭐ 方法1：用JS提取 - 使用1688搜索页面的实际CSS类
    try:
        items_data = page.evaluate(f"""
            () => {{
                const results = [];
                const seen = new Set();

                // 找到所有产品卡片
                const cards = document.querySelectorAll(
                    'div.search-offer-item, ' +
                    'div[class*="search-offer-item"], ' +
                    'div[class*="offer-item"]'
                );

                for (const card of cards) {{
                    if (results.length >= {max_products}) break;

                    // 获取产品详情链接
                    const titleRow = card.querySelector(
                        'div.offer-title-row a, ' +
                        'div[class*="offer-title"] a, ' +
                        'a[href*="detail.1688.com/offer/"], ' +
                        'a[href*="/offer/"][href*=".html"]'
                    );

                    if (!titleRow) continue;
                    let url = titleRow.href || '';
                    if (!url || seen.has(url)) continue;
                    seen.add(url);

                    // 获取标题文本
                    let title = (titleRow.getAttribute('title') || '').trim();
                    if (!title) {{
                        title = (titleRow.innerText || '').trim();
                    }}
                    if (!title || title.length < 4) continue;

                    // 获取主图
                    let imgUrl = '';
                    const imgWrapper = card.querySelector('div[class*="offer-img"] img');
                    if (imgWrapper) {{
                        imgUrl = imgWrapper.src || imgWrapper.getAttribute('data-src') || '';
                    }}

                    // 获取价格
                    let price = '';
                    const priceRow = card.querySelector('div[class*="offer-price"]');
                    if (priceRow) {{
                        price = (priceRow.innerText || '').trim();
                    }}

                    // 获取店铺名
                    let shop = '';
                    const shopRow = card.querySelector('div[class*="offer-shop"] a');
                    if (shopRow) {{
                        shop = (shopRow.innerText || '').trim();
                    }}

                    results.push({{
                        url: url,
                        title: title,
                        image_url: imgUrl,
                        price: price,
                        shop: shop,
                    }});
                }}

                return results;
            }}
        """)

        for item_data in items_data:
            url = item_data.get("url", "")
            title = item_data.get("title", "")
            if not url or not title:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            products.append({
                "title": title.strip(),
                "price": item_data.get("price", ""),
                "url": url,
                "image_url": item_data.get("image_url", ""),
                "shop": item_data.get("shop", ""),
                "keyword": keyword,
            })
            print(f"  📦 {title.strip()[:50]}")
            if len(products) >= max_products:
                break
    except Exception as e:
        print(f"  JS方法1失败: {e}")

    # ⭐ 方法2：如果JS方法没找到，用Playwright选择器
    if not products:
        print("  使用方法2（Playwright选择器）...")
        try:
            # 先用 offer-title-row
            cards = page.locator("div[class*='search-offer-item'], div[class*='offer-item']").all()
            print(f"  找到 {len(cards)} 个卡片")
            for card in cards[:max_products * 2]:
                try:
                    link = card.locator("a[href*='detail.1688.com/offer/'], a[href*='/offer/']").first
                    url = link.get_attribute("href") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = (link.get_attribute("title") or link.inner_text() or "").strip()
                    if not title or len(title) < 4:
                        continue

                    products.append({
                        "title": title,
                        "price": "",
                        "url": url,
                        "image_url": "",
                        "shop": "",
                        "keyword": keyword,
                    })
                    print(f"  📦 {title[:50]}")
                    if len(products) >= max_products:
                        break
                except:
                    continue
        except Exception as e:
            print(f"  方法2失败: {e}")

    # ⭐ 方法3：终极兜底 - 找所有offer链接
    if not products:
        print("  使用终极兜底方法...")
        try:
            links = page.locator("a[href*='offer/']").all()
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if "offer" not in href:
                        continue
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title = (link.get_attribute("title") or link.inner_text() or "").strip()
                    if len(title) < 5:
                        continue
                    if any(x in title for x in ["下一页", "上一页", "首页", "尾页", "确定", "重置", "排序", "筛选"]):
                        continue

                    if not href.startswith("http"):
                        href = urljoin("https:", href)

                    products.append({
                        "title": title,
                        "price": "",
                        "url": href,
                        "image_url": "",
                        "shop": "",
                        "keyword": keyword,
                    })
                    print(f"  📦 {title[:50]}")
                    if len(products) >= max_products:
                        break
                except:
                    continue
        except Exception as e:
            print(f"  方法3失败: {e}")

    print(f"  ✅ 找到 {len(products)} 个产品")
    return products


def scrape_product_detail(page, product: dict) -> ProductInfo:
    """打开产品详情页，提取详细信息"""
    info = ProductInfo()
    info.title = product["title"]
    info.price = product["price"]
    info.url = product["url"]
    info.shop_name = product["shop"]
    info.source_keyword = product["keyword"]
    info.id = extract_product_id(product["url"])
    info.main_image_url = product["image_url"]
    info.scrape_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  📋 正在采集详情：{info.title[:30]}...")

    try:
        page.goto(product["url"], timeout=config.PAGE_LOAD_TIMEOUT)
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 600)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        detail_selectors = [
            "div[class*='detail']", "div[class*='desc']", "div[id*='detail']",
            "div[id*='desc']", "div[class*='attributes']", "div[class*='parameter']",
        ]
        detail_parts = []
        for selector in detail_selectors:
            try:
                for el in page.locator(selector).all():
                    if el.is_visible(timeout=500):
                        text = el.inner_text()
                        if text and len(text) > 20:
                            detail_parts.append(text)
            except:
                continue
        info.detail_text = "\n".join(detail_parts[:5])

        # 提取店铺信息
        try:
            shop_el = page.locator("a[href*='shop'], a[href*='store'], span[class*='shop']").first
            if shop_el.is_visible(timeout=1000):
                shop_text = shop_el.inner_text().strip()
                if shop_text:
                    info.shop_name = shop_text
        except:
            pass

        # 提取销量
        try:
            sales_el = page.locator("span:has-text('成交'), span:has-text('销量'), span:has-text('笔')").first
            if sales_el.is_visible(timeout=1000):
                info.sales_info = sales_el.inner_text()
        except:
            pass

        # 下载主图
        if config.DOWNLOAD_IMAGES:
            try:
                imgs = page.locator("img[src*='.jpg'], img[src*='.png'], img[src*='.webp']").all()
                img_urls = []
                for img in imgs:
                    try:
                        if img.is_visible(timeout=500):
                            src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                            if src and src not in img_urls:
                                if src.startswith("//"):
                                    src = "https:" + src
                                img_urls.append(src)
                    except:
                        continue
                for idx, img_url in enumerate(img_urls[:3]):
                    local = download_image(img_url, config.IMAGES_DIR, info.id, idx)
                    if local:
                        if idx == 0:
                            info.main_image_local = local
                        else:
                            info.extra_images.append(img_url)
                            info.extra_images_local.append(local)
            except:
                pass

        info.category = auto_categorize(info.title, info.detail_text)
    except PlaywrightTimeout:
        print(f"    ⚠️ 页面加载超时")
    except Exception as e:
        print(f"    ❌ 采集出错：{e}")

    return info
