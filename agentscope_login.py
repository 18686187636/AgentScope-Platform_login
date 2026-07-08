#!/usr/bin/env python3
"""
修复登录检测等待问题，点击后等待足够时间
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

BUTTON_DEPLOY = os.getenv("BUTTON_DEPLOY", "一键配置QwenPaw")
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

def wait_for_login_success(page, timeout=30000):
    """轮询检测登录成功信号，最长等待 timeout 毫秒"""
    start = time.time()
    while (time.time() - start) * 1000 < timeout:
        # 检查URL是否跳离 /login
        if "/login" not in page.url:
            log("✅ 检测到 URL 跳转")
            return True
        # 检查是否有退出按钮
        if page.locator("button:has-text('退出'), a:has-text('退出')").count():
            log("✅ 检测到退出按钮")
            return True
        # 检查是否有错误信息
        if page.locator(".error, .alert, .message:has-text('错误')").count():
            err = page.locator(".error, .alert, .message:has-text('错误')").text_content()
            log(f"❌ 登录页面出现错误: {err}")
            return False
        time.sleep(2)  # 每2秒检查一次
    return False

def screenshot(page, name):
    try:
        page.screenshot(path=f"{name}.png")
        log(f"📸 截图: {name}.png")
    except:
        pass

def run():
    log("启动 Agentscope 自动登录（修复等待）")
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
                    raise RuntimeError("未找到 #account")

                password_input = page.wait_for_selector("#password", timeout=10000)
                if password_input:
                    password_input.fill(PASSWORD)
                    log("✅ 已填写密码")
                else:
                    raise RuntimeError("未找到 #password")

                # 验证码检测
                if page.locator("input[id*='captcha']").count():
                    log("⚠️ 检测到验证码")
                    screenshot(page, "captcha")
                    raise RuntimeError("验证码出现")

                submit_btn = page.wait_for_selector("button:has-text('登录'), button[type='submit']", timeout=10000)
                if submit_btn:
                    submit_btn.click()
                    log("⏳ 已点击登录按钮，等待登录成功...")
                else:
                    raise RuntimeError("未找到登录按钮")

                # 等待登录成功
                success = wait_for_login_success(page, timeout=20000)  # 20秒
                if not success:
                    screenshot(page, "login_timeout")
                    # 打印页面内容摘要
                    preview = page.content()[:500]
                    log(f"页面内容预览: {preview}")
                    raise RuntimeError("登录超时，未能检测到登录成功信号")

                log("✅ 登录成功")

            # 等待页面完全加载
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            screenshot(page, "after_login")

            # 点击“一键配置QwenPaw”
            try:
                deploy_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}')",
                    timeout=5000
                )
                if deploy_btn and deploy_btn.is_visible():
                    deploy_btn.click()
                    log(f"✅ 已点击 '{BUTTON_DEPLOY}'")
                    log("⏳ 等待 3 秒...")
                    time.sleep(3)
                else:
                    log(f"⚠️ 按钮 '{BUTTON_DEPLOY}' 不可见")
                    screenshot(page, "deploy_not_found")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_DEPLOY}'")
                screenshot(page, "deploy_timeout")

            # 点击“打开QWENPAW”
            try:
                qwen_btn = page.wait_for_selector(
                    f"button:has-text('{BUTTON_QWENPAW}'), a:has-text('{BUTTON_QWENPAW}')",
                    timeout=5000
                )
                if qwen_btn and qwen_btn.is_visible():
                    qwen_btn.click()
                    log(f"✅ 已点击 '{BUTTON_QWENPAW}'")
                    log("⏳ 等待 5 秒...")
                    time.sleep(5)
                else:
                    log(f"⚠️ 按钮 '{BUTTON_QWENPAW}' 不可见")
                    screenshot(page, "qwen_not_found")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_QWENPAW}'")
                screenshot(page, "qwen_timeout")

            log("🎉 脚本执行完毕")
            send_tg("✅ Agentscope 自动操作成功")

        except Exception as e:
            log(f"❌ 异常: {e}")
            screenshot(page, "error")
            send_tg(f"❌ 脚本失败: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本退出: {e}")
        sys.exit(1)
