"""
1688 Packaging Scraper Module
Fixed: no emoji, no networkidle timeout, GBK safe
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
        print(f"    [WARN] Image download failed: {e}")
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
        "Cardboard/Corrugated Box": [u"\u7eb8\u7bb1", u"\u74e6\u68f1", u"\u7eb8\u76d2", u"\u5feb\u9012\u7bb1", u"\u5305\u88c5\u7bb1", u"\u98de\u673a\u76d2", u"\u5f69\u7bb1"],
        "Gift Box/Color Box": [u"\u793c\u54c1\u76d2", u"\u793c\u76d2", u"\u5f69\u76d2", u"\u9996\u9970\u76d2", u"\u5316\u5986\u54c1\u76d2", u"\u5305\u88c5\u76d2", u"\u5929\u5730\u76d6"],
        "Food Packaging Bag": [u"\u98df\u54c1\u888b", u"\u98df\u54c1\u5305\u88c5", u"\u96f6\u98df\u888b", u"\u81ea\u7acb\u888b", u"\u62c9\u94fe\u888b", u"\u771f\u7a7a\u888b", u"\u8336\u53f6\u888b"],
        "Express/Mailing Bag": [u"\u5feb\u9012\u888b", u"\u7269\u6d41\u888b", u"\u6c14\u6ce1\u888b", u"\u5feb\u9012\u5305\u88c5", u"\u73e0\u5149\u819c\u888b"],
        "Handbag/Paper Bag": [u"\u624b\u63d0\u888b", u"\u7eb8\u888b", u"\u624b\u888b", u"\u793c\u54c1\u888b", u"\u8d2d\u7269\u888b", u"\u73af\u4fdd\u888b"],
        "Plastic Packaging": [u"\u5851\u6599\u888b", u"pe\u888b", u"opp\u888b", u"\u590d\u5408\u888b", u"\u5851\u6599\u819c", u"\u7f20\u7ed5\u819c", u"\u6536\u7f29\u819c"],
        "Label/Sticker": [u"\u4e0d\u5e72\u80f6", u"\u6807\u7b7e", u"\u8d34\u7eb8", u"\u6761\u5f62\u7801", u"\u540a\u724c"],
        "Packaging Accessories": [u"\u80f6\u5e26", u"\u6253\u5305\u5e26", u"\u7f20\u7ed5\u819c", u"\u6c14\u6ce1\u819c", u"\u73cd\u73e0\u68c9", u"\u62a4\u89d2", u"\u5e72\u71e5\u5242"],
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "Other Packaging"


def scrape_search_results(page, keyword: str, max_products: int) -> list:
    """
    Search 1688 for given keyword and return product list
    Fixed: no networkidle timeout, use domcontentloaded, no emoji
    """
    print(f"\n[INFO] Searching: {keyword}")
    search_url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}&n=y"

    # Use domcontentloaded instead of networkidle to avoid timeout
    try:
        page.goto(search_url, timeout=config.PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
    except:
        pass

    print("  [INFO] Waiting for product data...")
    time.sleep(5)

    # Try waiting for product links with JS polling
    try:
        loaded = page.wait_for_function("""
            () => {
                const links = document.querySelectorAll(
                    'a[href*="detail.1688.com/offer/"], ' +
                    'a[href*="//detail.1688.com/offer/"]'
                );
                let validCount = 0;
                for (const a of links) {
                    const t = (a.getAttribute('title') || a.innerText || '').trim();
                    if (t.length >= 5) validCount++;
                    if (validCount >= 3) return true;
                }
                return false;
            }
        """, timeout=20000)
    except:
        pass

    # Scroll to load more
    for _ in range(3):
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(config.SCROLL_PAUSE_TIME)
        except:
            break
    try:
        page.evaluate("window.scrollTo(0, 0)")
    except:
        pass
    time.sleep(1)

    products = []
    seen_urls = set()

    # Method 1: JS extraction
    try:
        items_data = page.evaluate(f"""
            () => {{
                const results = [];
                const seen = new Set();
                const cards = document.querySelectorAll(
                    'div.search-offer-item, ' +
                    'div[class*="search-offer-item"], ' +
                    'div[class*="offer-item"]'
                );
                for (const card of cards) {{
                    if (results.length >= {max_products}) break;
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
                    let title = (titleRow.getAttribute('title') || '').trim();
                    if (!title) {{ title = (titleRow.innerText || '').trim(); }}
                    if (!title || title.length < 4) continue;
                    let imgUrl = '';
                    const imgWrapper = card.querySelector('div[class*="offer-img"] img');
                    if (imgWrapper) {{ imgUrl = imgWrapper.src || imgWrapper.getAttribute('data-src') || ''; }}
                    let price = '';
                    const priceRow = card.querySelector('div[class*="offer-price"]');
                    if (priceRow) {{ price = (priceRow.innerText || '').trim(); }}
                    let shop = '';
                    const shopRow = card.querySelector('div[class*="offer-shop"] a');
                    if (shopRow) {{ shop = (shopRow.innerText || '').trim(); }}
                    results.push({{ url, title, image_url: imgUrl, price, shop }});
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
            print(f"  [OK] {title.strip()[:50]}")
            if len(products) >= max_products:
                break
    except Exception as e:
        print(f"  [WARN] Method 1 failed: {e}")

    # Method 2: Playwright selectors
    if not products:
        print("  [INFO] Using Method 2 (Playwright selectors)...")
        try:
            cards = page.locator("div[class*='search-offer-item'], div[class*='offer-item']").all()
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
                        "title": title, "price": "", "url": url,
                        "image_url": "", "shop": "", "keyword": keyword,
                    })
                    print(f"  [OK] {title[:50]}")
                    if len(products) >= max_products:
                        break
                except:
                    continue
        except Exception as e:
            print(f"  [WARN] Method 2 failed: {e}")

    # Method 3: Fallback
    if not products:
        print("  [INFO] Using fallback method...")
        try:
            links = page.locator("a[href*='offer/']").all()
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if "offer" not in href or href in seen_urls:
                        continue
                    seen_urls.add(href)
                    title = (link.get_attribute("title") or link.inner_text() or "").strip()
                    if len(title) < 5:
                        continue
                    skip_titles = [u"\u4e0b\u4e00\u9875", u"\u4e0a\u4e00\u9875", u"\u9996\u9875", u"\u5c3e\u9875", u"\u786e\u5b9a", u"\u91cd\u7f6e", u"\u6392\u5e8f", u"\u7b5b\u9009"]
                    if any(x in title for x in skip_titles):
                        continue
                    if not href.startswith("http"):
                        href = urljoin("https:", href)
                    products.append({
                        "title": title, "price": "", "url": href,
                        "image_url": "", "shop": "", "keyword": keyword,
                    })
                    print(f"  [OK] {title[:50]}")
                    if len(products) >= max_products:
                        break
                except:
                    continue
        except Exception as e:
            print(f"  [WARN] Method 3 failed: {e}")

    print(f"  [INFO] Found {len(products)} products")
    return products


def scrape_product_detail(page, product: dict) -> ProductInfo:
    """Open product detail page and extract info"""
    info = ProductInfo()
    info.title = product["title"]
    info.price = product["price"]
    info.url = product["url"]
    info.shop_name = product["shop"]
    info.source_keyword = product["keyword"]
    info.id = extract_product_id(product["url"])
    info.main_image_url = product["image_url"]
    info.scrape_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  [INFO] Scraping detail: {info.title[:30]}...")

    try:
        page.goto(product["url"], timeout=config.PAGE_LOAD_TIMEOUT)
        time.sleep(2)
        try:
            page.evaluate("window.scrollTo(0, 600)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        except:
            pass

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

        # Shop name
        try:
            shop_el = page.locator("a[href*='shop'], a[href*='store'], span[class*='shop']").first
            if shop_el.is_visible(timeout=1000):
                shop_text = shop_el.inner_text().strip()
                if shop_text:
                    info.shop_name = shop_text
        except:
            pass

        # Sales info
        try:
            sales_el = page.locator("span:has-text('transaction'), span:has-text('sales'), span:has-text('items')").first
            if sales_el.is_visible(timeout=1000):
                info.sales_info = sales_el.inner_text()
        except:
            pass

        # Download images
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
        print(f"    [WARN] Page load timeout")
    except Exception as e:
        print(f"    [ERROR] Scrape error: {e}")

    return info
