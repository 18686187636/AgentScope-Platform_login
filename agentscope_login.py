#!/usr/bin/env python3
"""
支持多账号，第二个按钮仅精确匹配“打开QWENPAW”，等待时间延长至45秒
"""
import os
import sys
import json
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")
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
            return True
        error = page.locator(".error, .alert, .message:has-text('错误')")
        if error.count():
            err_text = error.text_content()
            log(f"❌ 登录失败: {err_text}")
            return False
        time.sleep(2)
    return False

def click_button_exact(page, button_text, timeout=45000):
    """
    只精确匹配 button_text，等待最长 timeout 毫秒
    """
    try:
        btn = page.wait_for_selector(
            f"button:has-text('{button_text}'), a:has-text('{button_text}'), [role='button']:has-text('{button_text}')",
            state='visible',
            timeout=timeout
        )
        if btn:
            log(f"✅ 找到按钮 '{button_text}'")
            btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            try:
                btn.click()
                log(f"✅ 点击成功")
                return True
            except:
                page.evaluate("(element) => element.click()", btn)
                log(f"✅ JavaScript 点击成功")
                return True
    except PlaywrightTimeoutError:
        log(f"❌ 等待 '{button_text}' 超时（{timeout/1000}秒）")
        # 打印按钮列表帮助调试
        buttons = page.locator("button, a[role='button'], [role='button']")
        count = buttons.count()
        if count > 0:
            log("页面上找到的按钮文本：")
            for i in range(min(count, 20)):
                try:
                    text = buttons.nth(i).text_content()
                    log(f"  {i+1}: {text}")
                except:
                    pass
        return False

def process_account(username, password, account_index):
    log(f"--- 开始处理账号 {account_index}: {username} ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        try:
            log(f"🌐 访问登录页面: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            screenshot(page, f"01_login_{account_index}")

            token = page.evaluate("() => localStorage.getItem('accessToken')")
            if token:
                log(f"账号 {account_index} 已检测到 accessToken，跳过登录")
            else:
                log("📝 填写登录表单...")
                username_input = page.wait_for_selector("#account", timeout=10000)
                username_input.fill(username)
                log("✅ 已填写邮箱")
                screenshot(page, f"02_username_{account_index}")

                password_input = page.wait_for_selector("#password", timeout=10000)
                password_input.fill(password)
                log("✅ 已填写密码")
                screenshot(page, f"03_password_{account_index}")

                log("⏳ 按 Enter 键提交登录...")
                password_input.press("Enter")
                screenshot(page, f"04_after_enter_{account_index}")

                log("⏳ 等待 accessToken 出现...")
                success = wait_for_token(page, timeout=60000)
                if not success:
                    submit_btn = page.locator("button:has-text('登录'), button[type='submit']")
                    if submit_btn.count():
                        submit_btn.click()
                        success = wait_for_token(page, timeout=30000)
                if not success:
                    screenshot(page, f"05_login_failed_{account_index}")
                    raise RuntimeError(f"账号 {account_index} 登录失败")

            log(f"✅ 账号 {account_index} 登录成功")
            screenshot(page, f"06_logged_in_{account_index}")

            # 等待页面完全稳定
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(3)

            # 1. 点击第一个按钮
            log(f"🔍 尝试点击 '{BUTTON_DEPLOY}' ...")
            if not click_button_exact(page, BUTTON_DEPLOY, timeout=30000):
                screenshot(page, f"07_deploy_failed_{account_index}")
                raise RuntimeError(f"账号 {account_index} 无法点击 '{BUTTON_DEPLOY}'")
            screenshot(page, f"07_deploy_clicked_{account_index}")

            # 增加等待时间，让第二个按钮完全加载
            log("⏳ 等待 15 秒，确保页面加载完成...")
            time.sleep(15)
            page.wait_for_load_state("networkidle", timeout=15000)
            # 再额外等待 2 秒，给动态内容缓冲
            time.sleep(2)

            # 2. 点击第二个按钮（仅精确匹配，超时45秒）
            log(f"🔍 尝试点击 '{BUTTON_QWENPAW}' ...")
            if not click_button_exact(page, BUTTON_QWENPAW, timeout=45000):
                screenshot(page, f"08_qwen_failed_{account_index}")
                raise RuntimeError(f"账号 {account_index} 无法点击 '{BUTTON_QWENPAW}'")
            screenshot(page, f"08_qwen_clicked_{account_index}")
            log("⏳ 等待 5 秒...")
            time.sleep(5)

            log(f"🎉 账号 {account_index} 处理成功")
            browser.close()
            return True
        except Exception as e:
            log(f"❌ 账号 {account_index} 异常: {e}")
            screenshot(page, f"error_{account_index}")
            browser.close()
            return False

def run():
    accounts_json = os.getenv("ACCOUNTS_JSON", "")
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
        except:
            log("❌ 解析 ACCOUNTS_JSON 失败")
            sys.exit(1)
    else:
        username = os.getenv("AGENTSCOPE_USERNAME", "")
        password = os.getenv("AGENTSCOPE_PASSWORD", "")
        if not username or not password:
            log("❌ 未设置任何账号凭证")
            sys.exit(1)
        accounts = [{"username": username, "password": password}]

    success_count = 0
    fail_count = 0
    for idx, cred in enumerate(accounts, start=1):
        username = cred.get("username")
        password = cred.get("password")
        if not username or not password:
            log(f"⚠️ 账号 {idx} 缺少用户名或密码，跳过")
            continue
        if process_account(username, password, idx):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(2)

    log(f"处理完成：成功 {success_count} 个，失败 {fail_count} 个")
    if fail_count > 0:
        send_tg(f"❌ Agentscope 多账号处理完成，但 {fail_count} 个账号失败")
        sys.exit(1)
    else:
        send_tg(f"✅ Agentscope 所有 {success_count} 个账号处理成功")
        sys.exit(0)

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本退出: {e}")
        sys.exit(1)
