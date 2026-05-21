"""
1688 Login Module
Enhanced login state detection
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

import config


def login_automatically(page) -> bool:
    """Auto login with account/password"""
    if not config.USERNAME or not config.PASSWORD:
        print("[WARN] No 1688 credentials configured. Fill USERNAME/PASSWORD in config.py")
        return False

    print(f"[INFO] Auto-login 1688 (account: {config.USERNAME[:3]}***)")
    try:
        page.goto("https://login.1688.com/", timeout=config.PAGE_LOAD_TIMEOUT)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        except:
            pass
        time.sleep(2)

        # Switch to password login tab
        try:
            pwd_tab = page.locator("a:has-text('\u5bc6\u7801\u767b\u5f55')")
            if pwd_tab.is_visible(timeout=3000):
                pwd_tab.click()
                time.sleep(1)
        except:
            pass

        # Fill username
        try:
            username_input = page.locator("input[id*='username'], input[id*='account'], input[name*='user'], input[type='text'][placeholder*='phone']").first
            if username_input.is_visible(timeout=5000):
                username_input.fill(config.USERNAME)
                time.sleep(0.5)
        except:
            pass

        # Fill password
        try:
            pwd_input = page.locator("input[type='password'], input[id*='password']").first
            if pwd_input.is_visible(timeout=5000):
                pwd_input.fill(config.PASSWORD)
                time.sleep(0.5)
        except:
            pass

        # Click login button
        try:
            login_btn = page.locator("button[type='submit'], button:has-text('login'), a:has-text('login')").first
            if login_btn.is_visible(timeout=3000):
                login_btn.click()
        except:
            pass

        print("[INFO] Waiting for login (complete captcha manually if needed)...")
        time.sleep(5)

        current_url = page.url
        if "login" in current_url.lower():
            print("[WARN] Auto-login may not be complete, check for captcha")
            print("[INFO] Will continue in 15s, you can login manually...")
            for i in range(15, 0, -1):
                print(f"  Waiting {i}s...", end="\r")
                time.sleep(1)
            print()

        page.goto("https://www.1688.com/", timeout=config.PAGE_LOAD_TIMEOUT)
        time.sleep(3)

        if is_logged_in(page):
            print("[INFO] 1688 auto-login success!")
            return True
        else:
            print("[WARN] Auto-login failed, check credentials or login manually")
            return False

    except Exception as e:
        print(f"[ERROR] Auto-login error: {e}")
        return False


def manual_login(page) -> bool:
    """Manual login - open browser for user to login"""
    print("\n[INFO] Please login in the browser window")
    print("[INFO] If already logged in, skip this step\n")

    page.goto("https://www.1688.com/", timeout=config.PAGE_LOAD_TIMEOUT)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=30000)
    except:
        pass
    time.sleep(3)

    # Check multiple times
    for attempt in range(5):
        if is_logged_in(page):
            print("[INFO] Login state detected!")
            save_login_state(page)
            return True
        time.sleep(1)

    # Try clicking login button
    try:
        login_btn = page.locator("a:has-text('login'), span:has-text('login'), em:has-text('login')").first
        if login_btn.is_visible(timeout=3000):
            login_btn.click()
            time.sleep(2)
    except:
        pass

    print("[INFO] Waiting for login (max 90s)...")
    for i in range(90, 0, -1):
        if is_logged_in(page):
            print("\n[INFO] Login detected!")
            save_login_state(page)
            return True
        if i % 10 == 0:
            print(f"  Remaining {i}s...", end="\r")
        time.sleep(1)

    print("\n[WARN] Login timeout")
    return False


def is_logged_in(page) -> bool:
    """
    Check if logged in on 1688 (enhanced)
    6 methods, any hit = logged in
    """
    try:
        # Method 1: Check key link text
        for text in ["\u6211\u7684\u963f\u91cc", "\u6211\u76841688", "\u9000\u51fa", "\u91c7\u8d2d\u8f66", "\u6211\u7684\u91c7\u8d2d"]:
            try:
                el = page.locator(f"a:has-text('{text}'), span:has-text('{text}')").first
                if el.is_visible(timeout=500):
                    return True
            except:
                pass

        # Method 2: URL contains member or my
        url_lower = page.url.lower()
        if "member" in url_lower or "my.1688.com" in url_lower or "/my/" in url_lower:
            return True

        # Method 3: Check user avatar/nickname area
        try:
            user_area = page.locator("div[class*='user'], div[class*='member'], div[class*='login-success'], div[class*='header-user']").first
            if user_area.is_visible(timeout=500):
                return True
        except:
            pass

        # Method 4: Check for "please login" link (if not visible = logged in)
        try:
            login_prompt = page.locator("a:has-text('\u8bf7\u767b\u5f55'), span:has-text('\u8bf7\u767b\u5f55')").first
            if login_prompt.is_visible(timeout=500):
                return False
        except:
            pass

        # Method 5: Check cookies for login token via JS
        try:
            has_token = page.evaluate("""
                () => {
                    const cookies = document.cookie || '';
                    return cookies.includes('_tb_token_') || 
                           cookies.includes('cookie2') || 
                           cookies.includes('l');
                }
            """)
            if has_token:
                return True
        except:
            pass

        return False
    except:
        return False


def save_login_state(page):
    """Save browser login state"""
    state_path = config.LOGIN_STATE_DIR / "1688_login.json"
    page.context.storage_state(path=str(state_path))
    file_size = state_path.stat().st_size
    print(f"[INFO] Login state saved: {state_path} ({file_size} bytes)")
    return state_path


def ensure_login(page) -> bool:
    """
    Ensure login state - main entry
    Prefer loading saved state, skip if already logged in
    """
    print("[INFO] Verifying login state...")

    # Visit 1688 first
    page.goto("https://www.1688.com/", timeout=config.PAGE_LOAD_TIMEOUT)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=30000)
    except:
        pass
    time.sleep(5)

    if is_logged_in(page):
        print("[INFO] Already logged in, starting collection!")
        return True

    # Retry once
    print("[INFO] Refreshing page...")
    page.reload(wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    if is_logged_in(page):
        print("[INFO] Already logged in, starting collection!")
        return True

    # Try auto-login
    if config.USERNAME and config.PASSWORD:
        if login_automatically(page):
            save_login_state(page)
            return True

    # Finally: manual login
    return manual_login(page)
