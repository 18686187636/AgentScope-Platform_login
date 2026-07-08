#!/usr/bin/env python3
"""
使用 Cookie 自动登录 https://platform.agentscope.io/ 并点击“打开 QwenPaw”按钮
内置检查机制：Cookie 有效性、登录状态、按钮可用性、点击结果。
环境变量：
  AGENTSCOPE_COOKIE  - 登录后的 Cookie 字符串（必填），例如 "sessionid=abc; csrftoken=xyz"
  AGENTSCOPE_HEADLESS - 是否无头模式（默认 true）
  TG_BOT_TOKEN       - Telegram Bot Token（可选）
  TG_CHAT_ID         - Telegram Chat ID（可选）
"""

import os
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------- 配置 ----------
COOKIE_STR = os.getenv("AGENTSCOPE_COOKIE", "")
HEADLESS = os.getenv("AGENTSCOPE_HEADLESS", "true").lower() == "true"
LOGIN_URL = "https://platform.agentscope.io/"
TARGET_BUTTON_TEXT = "打开 QwenPaw"   # 可根据实际调整
# 登录后页面上的标志性元素（用于验证登录状态），若留空则使用默认检测（登录表单不存在）
LOGIN_SUCCESS_INDICATOR = os.getenv("LOGIN_SUCCESS_INDICATOR", "")  # 例如 ".user-avatar, .logout-btn"

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")

# ---------- 日志 ----------
def log(level: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# ---------- Telegram 通知 ----------
def send_telegram(message: str) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, json=data, timeout=30)
        resp.raise_for_status()
        log("INFO", "Telegram 消息发送成功")
        return True
    except Exception as e:
        log("ERROR", f"Telegram 发送失败: {e}")
        return False

# ---------- 解析 Cookie 字符串并提取过期信息 ----------
def parse_cookie_string(cookie_str: str, domain: str = "platform.agentscope.io"):
    """返回 (cookie_list, expiry_timestamps)"""
    cookies = []
    expiry_list = []
    for item in cookie_str.split(';'):
        item = item.strip()
        if not item or '=' not in item:
            continue
        key, value = item.split('=', 1)
        # 尝试解析过期时间（可能包含在 cookie 属性中，但通常 cookie 字符串不含 expires，只含 name=value）
        # 这里仅作记录，实际过期时间可在浏览器中查看或通过后端返回
        cookies.append({
            "name": key.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
            "httpOnly": False,
            "secure": False,
            "sameSite": "Lax"
        })
    return cookies

def check_cookie_expiry_from_browser(context):
    """通过浏览器上下文获取所有 cookie 的过期时间并计算剩余天数"""
    all_cookies = context.cookies()
    now = datetime.now(tz=timezone.utc)
    for c in all_cookies:
        if 'expires' in c and c['expires']:
            expiry_ts = c['expires']
            # Playwright 的 expires 是浮点数（秒），且是 UTC
            expiry_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
            remaining = expiry_dt - now
            days = remaining.total_seconds() / 86400
            log("INFO", f"Cookie '{c['name']}' 过期时间: {expiry_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')} (剩余 {days:.1f} 天)")
            if days < 3:
                log("WARN", f"⚠️ Cookie '{c['name']}' 将在 {days:.1f} 天后过期，请及时更新")
    return all_cookies

# ---------- 检查函数 ----------
def check_login_status(page) -> bool:
    """检查是否已登录。返回 True 表示已登录。"""
    # 1. 如果有自定义登录成功标志，优先使用
    if LOGIN_SUCCESS_INDICATOR:
        try:
            page.wait_for_selector(LOGIN_SUCCESS_INDICATOR, timeout=5000)
            log("INFO", "✅ 检测到登录成功标志元素")
            return True
        except PlaywrightTimeoutError:
            log("WARN", "未找到登录成功标志元素，可能未登录")
            return False

    # 2. 默认检测：页面中是否仍存在登录表单（密码输入框）
    password_input = page.locator("input[type='password']")
    if password_input.count():
        log("WARN", "页面仍存在登录表单，Cookie 可能无效")
        return False
    else:
        log("INFO", "✅ 未发现登录表单，假定已登录")
        return True

def check_button_exists(page, text: str) -> bool:
    """检查目标按钮是否存在且可见"""
    selector = (
        f"button:has-text('{text}'), "
        f"a:has-text('{text}'), "
        f"div:has-text('{text}') >> button, "
        f"[role='button']:has-text('{text}')"
    )
    try:
        btn = page.wait_for_selector(selector, timeout=5000)
        if btn.is_visible():
            log("INFO", f"✅ 目标按钮 '{text}' 存在且可见")
            return True
        else:
            log("WARN", f"目标按钮 '{text}' 存在但不可见")
            return False
    except PlaywrightTimeoutError:
        log("WARN", f"未找到目标按钮 '{text}'")
        return False

# ---------- 主函数 ----------
def run():
    log("INFO", "启动 Agentscope Cookie 自动登录脚本 (含检查机制)...")
    if not COOKIE_STR:
        log("ERROR", "请设置环境变量 AGENTSCOPE_COOKIE")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # ---------- 设置 Cookie ----------
        cookies = parse_cookie_string(COOKIE_STR, domain="platform.agentscope.io")
        log("INFO", f"添加 {len(cookies)} 个 Cookie")
        context.add_cookies(cookies)

        page = context.new_page()

        try:
            log("INFO", f"正在访问 {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            # ---------- 检查 1: Cookie 过期时间 ----------
            check_cookie_expiry_from_browser(context)

            # ---------- 检查 2: 登录状态 ----------
            if not check_login_status(page):
                page.screenshot(path="login_failed.png")
                raise RuntimeError("登录状态检查失败：Cookie 无效或已过期")

            # ---------- 检查 3: 目标按钮是否存在 ----------
            if not check_button_exists(page, TARGET_BUTTON_TEXT):
                page.screenshot(path="button_not_found.png")
                raise RuntimeError(f"未找到目标按钮 '{TARGET_BUTTON_TEXT}'")

            # ---------- 执行点击 ----------
            log("INFO", f"点击 '{TARGET_BUTTON_TEXT}' 按钮...")
            # 监听新窗口（如果点击打开新标签页）
            with context.expect_page() as new_page_info:
                # 使用更精确的选择器定位按钮并点击
                button_selector = (
                    f"button:has-text('{TARGET_BUTTON_TEXT}'), "
                    f"a:has-text('{TARGET_BUTTON_TEXT}'), "
                    f"div:has-text('{TARGET_BUTTON_TEXT}') >> button, "
                    f"[role='button']:has-text('{TARGET_BUTTON_TEXT}')"
                )
                page.click(button_selector, timeout=10000)
            # 等待可能的新窗口加载
            new_page = new_page_info.value
            if new_page:
                log("INFO", "✅ 点击后打开了新页面/新标签页")
                new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                log("INFO", f"新页面 URL: {new_page.url}")
                # 可额外检查新页面内容
            else:
                # 如果未打开新窗口，检查按钮是否消失或页面变化
                time.sleep(3)
                # 再次检查按钮是否还存在（如果按钮被移除或隐藏，视为成功）
                btn_after = page.locator(button_selector)
                if btn_after.count() == 0 or not btn_after.is_visible():
                    log("INFO", "✅ 按钮已消失，点击生效")
                else:
                    log("WARN", "点击后按钮仍存在，可能未成功触发，但脚本继续")

            log("INFO", "✅ 脚本执行成功")

            # 发送成功通知
            send_telegram(
                f"✅ <b>Agentscope 自动操作成功</b>\n"
                f"🍪 使用 Cookie 登录\n"
                f"⏱️ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📋 已点击 '{TARGET_BUTTON_TEXT}' 按钮"
            )

        except Exception as e:
            log("ERROR", f"执行异常: {e}")
            page.screenshot(path="error_screenshot.png")
            log("INFO", "错误截图已保存为 error_screenshot.png")
            send_telegram(
                f"❌ <b>Agentscope 自动操作失败</b>\n"
                f"⏱️ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📝 错误: {e}"
            )
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("WARN", "用户中断")
        sys.exit(130)
    except Exception as e:
        log("ERROR", f"脚本失败: {e}")
        sys.exit(1)
