# -*- coding: utf-8 -*-
"""Diagnostic script for 1688 search page"""
import time, json, sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent

def main():
    keyword = "手提盒定制厂家"
    print(">> Diagnostic search: " + keyword)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        state_path = BASE / "login_state" / "1688_login.json"
        storage = str(state_path) if state_path.exists() else None
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            storage_state=storage,
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()

        # Go to 1688 homepage
        print(">> Visiting 1688 homepage...")
        page.goto("https://www.1688.com/", timeout=60000, wait_until="networkidle")
        time.sleep(3)

        # Check login
        logged_in = page.evaluate("""() => {
            const text = document.body.innerText;
            return text.includes('\\u9000\\u51fa') || text.includes('\\u6211\\u7684\\u963f\\u91cc');
        }""")
        print(">> Logged in: " + str(logged_in))

        if not logged_in:
            print(">> Not logged in! Trying reload...")
            page.reload(wait_until="networkidle")
            time.sleep(5)
            logged_in = page.evaluate("""() => {
                const text = document.body.innerText;
                return text.includes('\\u9000\\u51fa') || text.includes('\\u6211\\u7684\\u963f\\u91cc');
            }""")
            print(">> After retry, logged in: " + str(logged_in))

        # Search
        print(">> Searching: " + keyword)
        search_url = "https://s.1688.com/selloffer/offer_search.htm?keywords=" + quote(keyword) + "&n=y"
        page.goto(search_url, timeout=60000, wait_until="networkidle")

        # Wait for products
        print(">> Waiting for product data (max 30s)...")
        start = time.time()
        loaded = False
        while time.time() - start < 30:
            has_products = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/offer/"]');
                const valid = [];
                for (const a of links) {
                    const href = a.href || '';
                    if (!href.includes('detail.1688.com') && !href.includes('//detail.1688.com')) continue;
                    const t = (a.getAttribute('title') || a.innerText || '').trim();
                    if (t.length >= 5) valid.push(t.substring(0, 30));
                }
                return valid;
            }""")

            if len(has_products) >= 3:
                print(">> Products loaded! Found " + str(len(has_products)) + " valid links")
                for i, t in enumerate(has_products[:5]):
                    print("  [" + str(i+1) + "] " + t)
                loaded = True
                break
            time.sleep(1)

        if not loaded:
            print(">> Current URL: " + page.url)
            print(">> TIMEOUT - products not loaded!")
            text = page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(">> Page text: " + text[:300])
            links_count = page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/offer/"]');
                return links.length;
            }""")
            print(">> Offer links on page: " + str(links_count))

            products = page.evaluate("""() => {
                const links = document.querySelectorAll('a');
                const results = [];
                const seen = new Set();
                for (const a of links) {
                    const href = a.href || '';
                    if (!href.includes('/offer/')) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const t = (a.getAttribute('title') || a.innerText || '').trim();
                    if (t.length >= 4) results.push(t.substring(0, 60));
                    if (results.length >= 10) break;
                }
                return results;
            }""")
            print(">> Raw offer link texts (" + str(len(products)) + "):")
            for p in products:
                print("  - " + p)
        else:
            products = page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                const links = document.querySelectorAll('a[href*="/offer/"]');
                for (const a of links) {
                    const href = a.href || '';
                    if (!href.includes('detail.1688.com') && !href.includes('//detail.1688.com')) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const t = (a.getAttribute('title') || a.innerText || '').trim();
                    if (t.length < 5) continue;
                    let price = '';
                    const card = a.closest('[class*="offer-item"], [class*="search-offer"], [class*="offer-list"]');
                    if (card) {
                        const priceEl = card.querySelector('[class*="price"]');
                        if (priceEl) price = (priceEl.innerText || '').trim();
                    }
                    results.push({
                        title: t.substring(0, 80),
                        url: href,
                        price: price.substring(0, 30),
                    });
                }
                return results;
            }""")

            print(">> SUCCESS! Extracted " + str(len(products)) + " products:")
            for p in products[:10]:
                print("  Product: " + p['title'])
                print("    Price: " + p['price'])

            json_path = BASE / "debug_products.json"
            json_path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding='utf-8')
            print(">> Saved to: " + str(json_path))

        print(">> Browser will close in 5 seconds...")
        time.sleep(3)
        browser.close()


if __name__ == "__main__":
    main()
