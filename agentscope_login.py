#!/usr/bin/env python3
"""
用户名/密码自动登录 platform.agentscope.io
按钮文字：一键配置QwenPaw、打开QWENPAW
点击每个按钮后分别等待（3秒和5秒）
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

BUTTON_DEPLOY = os.getenv("BUTTON_DEPLOY", "一键配置QwenPaw")
BUTTON_QWENPAW = os.getenv("BUTTON_QWENPAW", "打开QWENPAW")

LOGIN_URL = "https://platform.agentscope.io/login"
SUCCESS_INDICATOR = os.getenv("SUCCESS_INDICATOR", "")

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

def wait_for_login_success(page, timeout=30000):
    if SUCCESS_INDICATOR:
        try:
            page.wait_for_selector(SUCCESS_INDICATOR, timeout=timeout)
            log("✅ 检测到自定义登录成功标志")
            return True
        except PlaywrightTimeoutError:
            log("⚠️ 自定义标志未出现")

    if "/login" not in page.url:
        log("✅ URL 已跳转离开登录页")
        return True

    try:
        if page.locator("button:has-text('退出'), a:has-text('退出')").count():
            log("✅ 检测到退出按钮")
            return True
    except:
        pass

    try:
        title = page.title()
        if "控制台" in title or "Dashboard" in title or "平台" in title:
            log(f"✅ 页面标题包含登录后特征: {title}")
            return True
    except:
        pass

    error_msgs = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('失败')")
    if error_msgs.count():
        err_text = error_msgs.text_content()
        log(f"❌ 登录页面出现错误: {err_text}")
        return False

    return False

def run():
    log("启动 Agentscope 自动登录（按钮点击后分别等待 3s 和 5s）")
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

            if "/login" not in page.url:
                log("✅ 似乎已登录，跳过登录流程")
            else:
                log("📝 填写登录表单...")
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

                captcha_input = page.locator("input[id*='captcha'], input[placeholder*='验证码']")
                captcha_img = page.locator("img[alt*='captcha'], .captcha")
                if captcha_input.count() or captcha_img.count():
                    log("⚠️ 检测到验证码，自动登录无法处理")
                    page.screenshot(path="captcha_detected.png")
                    raise RuntimeError("页面出现验证码，请手动处理")

                submit_btn = page.wait_for_selector(
                    "button:has-text('登录'), button[type='submit']",
                    timeout=10000
                )
                if submit_btn:
                    submit_btn.click()
                    log("⏳ 已点击登录按钮，等待登录成功...")
                else:
                    raise RuntimeError("未找到登录按钮")

                success = wait_for_login_success(page, timeout=15000)
                if not success:
                    page.screenshot(path="login_timeout.png")
                    html_preview = page.content()[:500]
                    log(f"页面内容预览: {html_preview}")
                    error = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('失败')")
                    if error.count():
                        err_text = error.text_content()
                        log(f"❌ 登录失败: {err_text}")
                        raise RuntimeError(f"登录失败: {err_text}")
                    else:
                        raise RuntimeError("登录超时，未能检测到登录成功信号")

                log("✅ 登录成功")

            # 等待页面完全加载
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)

            # 1. 点击“一键配置QwenPaw”
            try:
                deploy_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}'), "
                    f"[role='button']:has-text('{BUTTON_DEPLOY}')",
                    timeout=5000
                )
                if deploy_btn and deploy_btn.is_visible():
                    deploy_btn.click()
                    log(f"✅ 已点击 '{BUTTON_DEPLOY}'，等待 3 秒...")
                    time.sleep(3)  # 等待 3 秒
                else:
                    log(f"⚠️ 按钮 '{BUTTON_DEPLOY}' 不可见")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_DEPLOY}'")
                page.screenshot(path="deploy_button_not_found.png")

            # 2. 点击“打开QWENPAW”
            try:
                qwen_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_QWENPAW}'), a:has-text('{BUTTON_QWENPAW}'), "
                    f"[role='button']:has-text('{BUTTON_QWENPAW}')",
                    timeout=5000
                )
                if qwen_btn and qwen_btn.is_visible():
                    qwen_btn.click()
                    log(f"✅ 已点击 '{BUTTON_QWENPAW}'，等待 5 秒...")
                    time.sleep(5)  # 等待 5 秒
                else:
                    log(f"⚠️ 按钮 '{BUTTON_QWENPAW}' 不可见")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_QWENPAW}'")
                page.screenshot(path="qwen_button_not_found.png")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功（两个按钮均已点击）")

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
