#!/usr/bin/env python3
"""
使用用户名/密码自动登录 platform.agentscope.io。
如果遇到验证码，则会截图并报错。
登录后点击"一键部署"按钮，然后点击"打开 QwenPaw"按钮。
"""
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# ---------- 从环境变量读取 ----------
USERNAME = os.getenv("AGENTSCOPE_USERNAME", "")
PASSWORD = os.getenv("AGENTSCOPE_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

LOGIN_URL = "https://platform.agentscope.io/"
TARGET_BUTTONS = [
    "一键部署",      # 先点这个
    "打开 QwenPaw"   # 再点这个
]

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
    log("启动 Agentscope 自动登录脚本（用户名/密码模式）")
    if not USERNAME or not PASSWORD:
        log("❌ 请设置环境变量 AGENTSCOPE_USERNAME 和 AGENTSCOPE_PASSWORD")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            log("🌐 访问登录页面...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(2)

            # 检查是否已经登录（如果已经有有效 session）
            if page.locator("button:has-text('登录')").count() == 0:
                log("✅ 似乎已登录，跳过登录流程")
            else:
                log("📝 填写登录表单...")
                # 定位用户名/邮箱输入框
                username_input = page.wait_for_selector(
                    "input[name='username'], input[type='text'], input[placeholder*='用户名'], input[placeholder*='邮箱']",
                    timeout=10000
                )
                username_input.fill(USERNAME)

                # 定位密码输入框
                password_input = page.wait_for_selector(
                    "input[name='password'], input[type='password']",
                    timeout=10000
                )
                password_input.fill(PASSWORD)

                # 检查是否有验证码
                captcha_element = page.locator("img[alt*='captcha'], .captcha, #captcha, [class*='captcha']")
                if captcha_element.count():
                    log("⚠️ 检测到验证码！自动登录无法处理验证码。")
                    page.screenshot(path="captcha_detected.png")
                    raise RuntimeError("页面出现验证码，无法自动登录，请手动处理或使用其他方案。")

                # 点击登录按钮
                submit_btn = page.wait_for_selector(
                    "button[type='submit'], button:has-text('登录'), button:has-text('Sign in')",
                    timeout=10000
                )
                submit_btn.click()
                log("⏳ 已提交登录，等待跳转...")

                # 等待登录成功（URL 变化或出现用户元素）
                try:
                    page.wait_for_url(lambda url: url != LOGIN_URL, timeout=15000)
                    log("✅ 登录成功，已跳转")
                except PlaywrightTimeoutError:
                    # 检查是否有错误信息
                    error_msg = page.locator(".error, .alert, .message:has-text('错误')")
                    if error_msg.count():
                        err_text = error_msg.text_content()
                        log(f"❌ 登录失败: {err_text}")
                        page.screenshot(path="login_error.png")
                        raise RuntimeError(f"登录失败: {err_text}")
                    else:
                        log("⚠️ 登录后 URL 未变，但未发现错误，继续尝试点击按钮...")

            # 登录成功后，点击按钮
            log("🔍 查找目标按钮...")
            for btn_text in TARGET_BUTTONS:
                try:
                    btn = page.wait_for_selector(
                        f"button:has-text('{btn_text}'), a:has-text('{btn_text}'), "
                        f"div:has-text('{btn_text}') >> button, [role='button']:has-text('{btn_text}')",
                        timeout=5000
                    )
                    if btn and btn.is_visible():
                        btn.click()
                        log(f"✅ 已点击 '{btn_text}'")
                        time.sleep(2)  # 等待点击后页面响应
                    else:
                        log(f"⚠️ 按钮 '{btn_text}' 不可见")
                except PlaywrightTimeoutError:
                    log(f"⚠️ 未找到按钮 '{btn_text}'")
                    # 截图以便调试
                    page.screenshot(path=f"button_{btn_text}_not_found.png")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功（用户名密码登录）")

        except Exception as e:
            log(f"❌ 执行异常: {e}")
            page.screenshot(path="error_screenshot.png")
            send_tg(f"❌ Agentscope 脚本失败\n错误: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本失败: {e}")
        sys.exit(1)
