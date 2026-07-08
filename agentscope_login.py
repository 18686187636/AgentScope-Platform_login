#!/usr/bin/env python3
"""
使用多种策略定位“一键部署QwenPaw”和“打开QWENPAW”按钮
支持文本包含匹配、类名匹配等
"""
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

USERNAME = os.getenv("AGENTSCOPE_USERNAME", "")
PASSWORD = os.getenv("AGENTSCOPE_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

# 按钮文本（环境变量可覆盖）
BUTTON_DEPLOY = os.getenv("BUTTON_DEPLOY", "一键部署QwenPaw")
BUTTON_QWENPAW = os.getenv("BUTTON_QWENPAW", "打开QWENPAW")

LOGIN_URL = "https://platform.agentscope.io/login"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            log(f"Telegram 发送失败: {e}")

def screenshot(page, name):
    try:
        page.screenshot(path=f"{name}.png")
        log(f"📸 截图: {name}.png")
    except Exception as e:
        log(f"截图失败 {name}: {e}")

def wait_for_token(page, timeout=60000):
    start = time.time()
    while (time.time() - start) < timeout / 1000:
        token = page.evaluate("() => localStorage.getItem('accessToken')")
        if token:
            log("✅ 检测到 accessToken，登录成功")
            return True
        error = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('失败')")
        if error.count():
            err_text = error.text_content()
            log(f"❌ 登录失败: {err_text}")
            return False
        time.sleep(2)
    return False

def click_button(page, button_text, timeout=15000):
    """
    使用多种策略点击按钮
    """
    strategies = [
        f"button:has-text('{button_text}')",
        f"a:has-text('{button_text}')",
        f"[role='button']:has-text('{button_text}')",
        # 不区分大小写
        f"button:has-text('{button_text}')",  # Playwright 默认不区分大小写
        # 包含匹配（如果文本有前后缀）
        f"button:has-text('{button_text}')",
        # 通过部分文本匹配（比如只匹配“部署”和“QwenPaw”）
        f"button:has-text('QwenPaw')",
        f"button:has-text('部署')",
        f"button:has-text('配置')",
        # 通过 class 或 id（如果需要，可以添加具体类名）
    ]
    # 尝试每个策略
    for selector in strategies:
        try:
            btn = page.locator(selector)
            if btn.count() > 0:
                # 检查是否可见
                if btn.is_visible():
                    btn.click()
                    log(f"✅ 使用选择器 '{selector}' 点击成功")
                    return True
                else:
                    log(f"⚠️ 选择器 '{selector}' 匹配但不可见")
        except:
            continue
    # 如果所有策略失败，打印页面上的所有按钮文本帮助调试
    log("⚠️ 所有定位策略失败，尝试获取页面上所有按钮的文本...")
    buttons = page.locator("button, a[role='button'], [role='button']")
    count = buttons.count()
    if count > 0:
        for i in range(min(count, 10)):
            try:
                text = buttons.nth(i).text_content()
                log(f" 按钮{i+1}: {text}")
            except:
                pass
    else:
        log("页面未找到任何按钮元素")
    return False

def run():
    log("启动 Agentscope 自动登录（多策略按钮定位）")
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
            screenshot(page, "01_login_page")

            token = page.evaluate("() => localStorage.getItem('accessToken')")
            if token:
                log("✅ 已检测到 accessToken，跳过登录")
            else:
                log("📝 填写登录表单...")
                username_input = page.wait_for_selector("#account", timeout=10000)
                username_input.fill(USERNAME)
                log("✅ 已填写邮箱")
                screenshot(page, "02_username_filled")

                password_input = page.wait_for_selector("#password", timeout=10000)
                password_input.fill(PASSWORD)
                log("✅ 已填写密码")
                screenshot(page, "03_password_filled")

                log("⏳ 按 Enter 键提交登录...")
                password_input.press("Enter")
                screenshot(page, "04_after_enter")

                log("⏳ 等待 accessToken 出现...")
                success = wait_for_token(page, timeout=60000)
                if not success:
                    # 尝试点击登录按钮作为备选
                    log("⚠️ Enter 提交未生效，尝试点击登录按钮...")
                    submit_btn = page.locator("button:has-text('登录'), button[type='submit']")
                    if submit_btn.count():
                        submit_btn.click()
                        success = wait_for_token(page, timeout=30000)

                if not success:
                    screenshot(page, "05_login_failed")
                    storage = page.evaluate("() => localStorage")
                    log(f"当前 localStorage 内容: {storage}")
                    raise RuntimeError("登录超时或失败，未检测到 accessToken")

            log("✅ 登录成功")
            screenshot(page, "06_logged_in")

            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(3)  # 等待页面完全渲染

            # 第一步：点击第一个按钮
            log(f"🔍 尝试点击 '{BUTTON_DEPLOY}' ...")
            success = click_button(page, BUTTON_DEPLOY, timeout=15000)
            if not success:
                screenshot(page, "07_deploy_failed")
                raise RuntimeError(f"无法点击 '{BUTTON_DEPLOY}' 按钮")
            else:
                screenshot(page, "07_deploy_clicked")
                log("⏳ 等待 5 秒，让第二个按钮出现...")
                time.sleep(5)

            # 第二步：点击第二个按钮
            log(f"🔍 尝试点击 '{BUTTON_QWENPAW}' ...")
            success = click_button(page, BUTTON_QWENPAW, timeout=15000)
            if not success:
                screenshot(page, "08_qwen_failed")
                raise RuntimeError(f"无法点击 '{BUTTON_QWENPAW}' 按钮")
            else:
                screenshot(page, "08_qwen_clicked")
                log("⏳ 等待 5 秒...")
                time.sleep(5)

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功")

        except Exception as e:
            log(f"❌ 异常: {e}")
            screenshot(page, "error")
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
