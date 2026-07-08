#!/usr/bin/env python3
"""
用户名/密码登录，以“一键配置QwenPaw”按钮出现作为登录成功标志
增加详细日志和截图，便于调试
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

def screenshot(page, name):
    try:
        page.screenshot(path=f"{name}.png")
        log(f"📸 截图: {name}.png")
    except Exception as e:
        log(f"截图失败 {name}: {e}")

def run():
    log("启动 Agentscope 自动登录（等待目标按钮出现）")
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

            # 如果已经登录（URL 不在 /login）
            if "/login" not in page.url:
                log("✅ 似乎已登录，跳过登录流程")
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

                # 点击登录按钮
                submit_btn = page.wait_for_selector(
                    "button:has-text('登录'), button[type='submit']",
                    timeout=10000
                )
                submit_btn.click()
                log("⏳ 已点击登录按钮，等待登录成功...")
                screenshot(page, "04_after_click")

                # 等待“一键配置QwenPaw”按钮出现（登录成功的标志）
                try:
                    # 尝试等待该按钮，最多等待 30 秒
                    page.wait_for_selector(
                        f"button:has-text('{BUTTON_DEPLOY}'), a:has-text('{BUTTON_DEPLOY}')",
                        timeout=30000
                    )
                    log("✅ 检测到 '一键配置QwenPaw' 按钮，登录成功！")
                    screenshot(page, "05_login_success")
                except PlaywrightTimeoutError:
                    # 超时：登录可能失败，检查错误信息
                    screenshot(page, "06_login_timeout")
                    # 检查是否有错误提示
                    error = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('失败')")
                    if error.count():
                        err_text = error.text_content()
                        log(f"❌ 登录失败: {err_text}")
                        raise RuntimeError(f"登录失败: {err_text}")
                    else:
                        # 没有错误提示，但按钮未出现，可能是页面未加载完成
                        html_preview = page.content()[:500]
                        log(f"页面内容预览: {html_preview}")
                        raise RuntimeError("登录超时：未检测到 '一键配置QwenPaw' 按钮，可能账号密码错误或页面异常")

            # 登录成功后，点击第二个按钮“打开QWENPAW”
            log("🔍 查找 '打开QWENPAW'...")
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
                    screenshot(page, "07_qwen_clicked")
                else:
                    log(f"⚠️ 按钮 '{BUTTON_QWENPAW}' 不可见")
                    screenshot(page, "07_qwen_not_found")
            except PlaywrightTimeoutError:
                log(f"⚠️ 未找到按钮 '{BUTTON_QWENPAW}'")
                screenshot(page, "07_qwen_not_found")

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
