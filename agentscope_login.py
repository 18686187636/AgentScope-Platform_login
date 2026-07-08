#!/usr/bin/env python3
"""
用户名/密码自动登录 platform.agentscope.io
根据实际 HTML 结构：id="account"、id="password"、按钮文本"登录"
"""
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# ---------- 环境变量 ----------
USERNAME = os.getenv("AGENTSCOPE_USERNAME", "")
PASSWORD = os.getenv("AGENTSCOPE_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

# 按钮文字（可根据实际调整）
BUTTON_DEPLOY = os.getenv("BUTTON_DEPLOY", "一键部署")
BUTTON_QWENPAW = os.getenv("BUTTON_QWENPAW", "打开 QwenPaw")

LOGIN_URL = "https://platform.agentscope.io/login"  # 直接访问登录页

# ---------- 函数 ----------
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            log(f"Telegram 发送失败: {e}")

def run():
    log("启动 Agentscope 自动登录（基于 id 选择器）")
    if not USERNAME or not PASSWORD:
        log("❌ 请设置 AGENTSCOPE_USERNAME 和 AGENTSCOPE_PASSWORD")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        try:
            log(f"🌐 访问登录页面: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)

            # 检查是否已经登录（如果 URL 跳转到主页或其他页面）
            if "/login" not in page.url:
                log("✅ 似乎已登录，跳过登录流程")
            else:
                log("📝 填写登录表单...")
                # 使用精确定位：id="account" 和 id="password"
                username_input = page.wait_for_selector("#account", timeout=10000)
                if username_input:
                    username_input.fill(USERNAME)
                    log("✅ 已填写邮箱")
                else:
                    raise RuntimeError("未找到 #account 输入框")

                password_input = page.wait_for_selector("#password", timeout=10000)
                if password_input:
                    password_input.fill(PASSWORD)
                    log("✅ 已填写密码")
                else:
                    raise RuntimeError("未找到 #password 输入框")

                # 检查验证码（仅简单检测，可能不准确）
                captcha = page.locator("img[alt*='captcha'], .captcha, [class*='captcha']")
                if captcha.count():
                    log("⚠️ 检测到验证码，自动登录无法处理")
                    page.screenshot(path="captcha_detected.png")
                    raise RuntimeError("页面出现验证码，请手动处理")

                # 点击登录按钮（文本为“登录”）
                submit_btn = page.wait_for_selector(
                    "button:has-text('登录'), button[type='submit']",
                    timeout=10000
                )
                if submit_btn:
                    submit_btn.click()
                    log("⏳ 已点击登录按钮，等待跳转...")
                else:
                    raise RuntimeError("未找到登录按钮")

                # 等待登录成功（URL 变化或出现主页元素）
                try:
                    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
                    log("✅ 登录成功，已跳转")
                except PlaywrightTimeoutError:
                    # 检查错误信息
                    error = page.locator(".error, .alert, .message:has-text('错误')")
                    if error.count():
                        err_text = error.text_content()
                        log(f"❌ 登录失败: {err_text}")
                        page.screenshot(path="login_error.png")
                        raise RuntimeError(f"登录失败: {err_text}")
                    else:
                        log("⚠️ URL 未变但无错误，可能登录成功，继续尝试点击按钮...")

            # 登录成功后，点击“一键部署”和“打开 QwenPaw”
            for btn_text in [BUTTON_DEPLOY, BUTTON_QWENPAW]:
                try:
                    btn = page.wait_for_selector(
                        f"button:has-text('{btn_text}'), a:has-text('{btn_text}'), "
                        f"[role='button']:has-text('{btn_text}')",
                        timeout=5000
                    )
                    if btn and btn.is_visible():
                        btn.click()
                        log(f"✅ 已点击 '{btn_text}'")
                        time.sleep(2)
                    else:
                        log(f"⚠️ 按钮 '{btn_text}' 不可见")
                except PlaywrightTimeoutError:
                    log(f"⚠️ 未找到按钮 '{btn_text}'")
                    page.screenshot(path=f"button_{btn_text}_not_found.png")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功")

        except Exception as e:
            log(f"❌ 异常: {e}")
            page.screenshot(path="error_screenshot.png")
            send_tg(f"❌ Agentscope 脚本失败\n错误: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本退出: {e}")
        sys.exit(1)
