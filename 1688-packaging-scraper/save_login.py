"""
一键手动登录并保存状态
使用系统已安装的 Edge 浏览器，解决白屏问题
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    print("=" * 60)
    print("  🌐 1688 手动登录 - 状态保存工具 v3")
    print("=" * 60)
    print("\n📌 使用 Edge 浏览器打开1688")
    print("  您手动登录后保存状态，以后自动复用\n")

    with sync_playwright() as p:
        # 使用系统自带的 Edge 浏览器（解决Chromium白屏问题）
        browser = p.chromium.launch(
            headless=False,
            channel="msedge",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-web-security",
            ]
        )
        # 先尝试加载已有的登录状态（避免重复登录）
        saved_state_path = Path(__file__).parent / "login_state" / "1688_login.json"
        storage_state_arg = str(saved_state_path) if saved_state_path.exists() else None

        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            storage_state=storage_state_arg,  # 加载已有状态
        )

        # 隐藏自动化标记
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = context.new_page()

        # 直接打开1688首页
        print("🌐 正在用 Edge 浏览器打开 1688.com ...")
        page.goto("https://www.1688.com/", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # 检查是否已登录
        try:
            if page.locator("a:has-text('我的阿里')").is_visible(timeout=3000):
                print("✅ 检测到已登录！")
                input("  按 Enter 保存登录状态...")
                self_save(context)
                browser.close()
                return
        except:
            pass

        # 点击登录按钮
        try:
            login_btn = page.locator("a:has-text('登录'), span:has-text('登录'), em:has-text('请登录')").first
            if login_btn.is_visible(timeout=5000):
                login_btn.click()
                print("✅ 已点击登录按钮")
                time.sleep(3)
        except:
            print("  尝试点击登录按钮")

        print("\n" + "=" * 60)
        print("  👆 请在 Edge 浏览器中手动完成登录：")
        print("  1. 输入账号密码   2. 滑验证码")
        print("  登录成功后，回到这里按 回车键 继续")
        print("=" * 60)
        input("  按 Enter 继续...")

        # 保存登录状态
        self_save(context)
        browser.close()

    print("\n🎉 完成！现在可以运行 python main.py 自动采集了！")


def self_save(context):
    state_dir = Path(__file__).parent / "login_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "1688_login.json"
    context.storage_state(path=str(state_path))
    file_size = state_path.stat().st_size
    print(f"\n✅ 登录状态已保存到：{state_path}")
    print(f"📂 文件大小：{file_size} 字节")
    if file_size > 200:
        print("✅ 保存成功！下次运行 main.py 会自动使用。")
    else:
        print("⚠️ 状态文件较小，请确认登录成功")


if __name__ == "__main__":
    main()
