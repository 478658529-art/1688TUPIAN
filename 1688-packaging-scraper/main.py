"""
1688 Packaging Hot Product Scraper - Main Entry
Runs daily at 9:00 AM (scheduled by Windows Task Scheduler)
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from playwright.sync_api import sync_playwright

import config
import login
import scraper
import reporter

# Image analysis module (enabled if opencv + pillow installed)
try:
    from image_analyzer import analyze_all_images
    HAS_ANALYZER = True
except ImportError:
    HAS_ANALYZER = False


def show_banner():
    """Show startup banner (no emoji, safe for all consoles)"""
    print("=" * 60)
    print("  1688 Packaging Factory Hot Product Collector")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    sys.stdout.flush()


def get_random_keywords(all_keywords: list, count: int = 5) -> list:
    """Randomly pick keywords from list"""
    import random
    random.seed(int(time.time()))
    return random.sample(all_keywords, min(count, len(all_keywords)))


def main():
    show_banner()

    # Create output directories
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # -- 1. Initialize browser --
    print("\n[INFO] Launching browser...")
    sys.stdout.flush()
    browser = None
    try:
        with sync_playwright() as p:
            # Launch browser (use system Edge)
            browser = p.chromium.launch(
                headless=config.HEADLESS,
                channel="msedge",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security",
                ]
            )

            # Load saved login state
            saved_state_path = config.LOGIN_STATE_DIR / "1688_login.json"
            storage_state_arg = str(saved_state_path) if saved_state_path.exists() else None
            if storage_state_arg:
                print(f"[INFO] Loaded saved login state: {saved_state_path}")
                sys.stdout.flush()

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                storage_state=storage_state_arg,
            )

            page = context.new_page()

            # -- 2. Login --
            print("\n[INFO] Logging in 1688...")
            sys.stdout.flush()
            logged_in = login.ensure_login(page)
            if not logged_in:
                print("[ERROR] Login failed, cannot proceed")
                sys.stdout.flush()
                return

            # -- 3. Scrape products --
            all_products = []
            used_keywords = []

            # Pick random keywords for today
            today_keywords = get_random_keywords(config.PACKAGING_KEYWORDS, 8)
            print(f"\n[INFO] Today will search {len(today_keywords)} keywords")
            sys.stdout.flush()

            for kw in today_keywords:
                if len(all_products) >= config.MAX_PRODUCTS_TOTAL:
                    print(f"[INFO] Daily limit ({config.MAX_PRODUCTS_TOTAL}) reached, stopping")
                    sys.stdout.flush()
                    break

                remaining = config.MAX_PRODUCTS_TOTAL - len(all_products)
                per_keyword = min(config.MAX_PRODUCTS_PER_KEYWORD, remaining)

                results = scraper.scrape_search_results(page, kw, per_keyword)
                used_keywords.append({"keyword": kw, "found": len(results)})

                for idx, product in enumerate(results):
                    if len(all_products) >= config.MAX_PRODUCTS_TOTAL:
                        break

                    print(f"  [{len(all_products)+1}/{config.MAX_PRODUCTS_TOTAL}] Scraping product {idx+1}/{len(results)}...")
                    sys.stdout.flush()
                    info = scraper.scrape_product_detail(page, product)
                    all_products.append(info.to_dict())
                    time.sleep(1.5)

            print(f"\n{'='*50}")
            print(f"[INFO] Collection complete! Got {len(all_products)} products")
            sys.stdout.flush()

            # -- 4. Save data --
            today_str = datetime.now().strftime("%Y-%m-%d")

            json_path = config.OUTPUT_DIR / f"products_{today_str}.json"
            json_path.write_text(json.dumps(all_products, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[INFO] Data saved: {json_path}")
            sys.stdout.flush()

            # -- 4b. Image analysis --
            if config.ENABLE_IMAGE_ANALYSIS and HAS_ANALYZER:
                print("\n[INFO] Running image analysis...")
                sys.stdout.flush()
                all_products = analyze_all_images(all_products)

                analyzed_json_path = config.OUTPUT_DIR / f"analyzed_{today_str}.json"
                analyzed_json_path.write_text(
                    json.dumps(all_products, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"[INFO] Analysis data saved: {analyzed_json_path}")
                sys.stdout.flush()

                reporter.generate_analysis_report(all_products, config.REPORTS_DIR / f"analysis_{today_str}.json")
                print("[INFO] Analysis report generated")
                sys.stdout.flush()
            else:
                print("\n[INFO] Image analysis not enabled (install opencv-python + pillow)")
                sys.stdout.flush()

            # -- 5. Generate reports --
            print(f"\n[INFO] Generating reports...")
            sys.stdout.flush()

            html_path = config.REPORTS_DIR / f"report_{today_str}.html"
            reporter.generate_html_report(all_products, html_path)
            print(f"[INFO] HTML report: {html_path}")
            sys.stdout.flush()

            excel_path = config.REPORTS_DIR / f"report_{today_str}.xlsx"
            reporter.generate_excel_report(all_products, excel_path)
            print(f"[INFO] Excel report: {excel_path}")
            sys.stdout.flush()

            # -- 6. Summary --
            print(f"\n{'='*50}")
            print(f"[SUMMARY] Today's Collection")
            print(f"{'='*50}")
            print(f"  Keywords searched: {len(used_keywords)}")
            for uk in used_keywords:
                print(f"    - {uk['keyword']}: found {uk['found']} products")
            print(f"  Total products: {len(all_products)}")
            sys.stdout.flush()

            categorized = defaultdict(list)
            for p in all_products:
                categorized[p.get("category", "Other")].append(p)
            print(f"\n  Categories:")
            for cat, items in sorted(categorized.items(), key=lambda x: -len(x[1])):
                print(f"    {cat}: {len(items)} items")
            print(f"\n  HTML Report: {html_path}")
            print(f"  Excel Report: {excel_path}")
            print(f"\n[INFO] All done!")
            sys.stdout.flush()

            if not config.HEADLESS:
                print("\n[INFO] Browser will close in 10 seconds...")
                sys.stdout.flush()
                time.sleep(10)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.stdout.flush()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
    finally:
        if browser:
            try:
                browser.close()
                print("[INFO] Browser closed")
                sys.stdout.flush()
            except:
                pass


if __name__ == "__main__":
    main()
