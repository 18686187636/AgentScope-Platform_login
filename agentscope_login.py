#!/usr/bin/env python3
"""
多账号脚本 - 自适应中英文按钮，生成详细 Telegram 报告（北京时间）
改进说明：
1. 按钮匹配改为关键词部分匹配（不区分大小写），自动适配中英文
2. 增加对登录提交按钮的显式点击，提高登录成功率
3. 增加更智能的等待策略（等待特定元素变化，而非固定 sleep）
4. 支持环境变量 BUTTON_DEPLOY 和 BUTTON_QWENPAW 作为关键词列表（逗号分隔）
5. 默认关键词已包含中英文，无需额外配置
"""

import os
import sys
import json
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, timezone, timedelta

# ---------- 时区设置 ----------
BEIJING_TZ = timezone(timedelta(hours=8))

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

# 读取环境变量作为关键词列表，若未设置则使用默认（中英文混合）
DEPLOY_RAW = os.getenv("BUTTON_DEPLOY", "Deploy QwenPaw,一键部署 QwenPaw,部署,Deploy")
DEPLOY_KEYWORDS = [t.strip() for t in DEPLOY_RAW.split(',') if t.strip()]

QWEN_RAW = os.getenv("BUTTON_QWENPAW", "Open QWENPAW,打开 QWENPAW,QwenPaw")
QWEN_KEYWORDS = [t.strip() for t in QWEN_RAW.split(',') if t.strip()]

LOGIN_URL = "https://platform.agentscope.io/login"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_tg(msg):
    """发送 Telegram 消息（纯文本）"""
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": msg}, timeout=10)
        except Exception as e:
            log(f"Telegram 发送失败: {e}")

def screenshot(page, name):
    try:
        page.screenshot(path=f"{name}.png")
        log(f"📸 截图: {name}.png")
    except Exception as e:
        log(f"截图失败 {name}: {e}")

def wait_for_token(page, timeout=60000):
    """
    等待 localStorage 中出现 accessToken，同时检测可能的错误信息
    """
    try:
        page.wait_for_function(
            "() => localStorage.getItem('accessToken') !== null",
            timeout=timeout
        )
        return True
    except PlaywrightTimeoutError:
        # 检查是否有错误提示
        error_elem = page.locator(".error, .alert, .message:has-text('错误'), .message:has-text('Error')")
        if error_elem.count():
            err_text = error_elem.first.text_content()
            log(f"❌ 登录失败: {err_text}")
        return False

def click_button_by_keywords(page, keywords, timeout_per_attempt=10000, total_timeout=60000):
    """
    根据关键词列表（部分匹配，不区分大小写）点击按钮。
    支持 button, a[role='button'], [role='button'] 等元素。
    返回 True 表示成功点击，False 表示超时或未找到。
    """
    start_time = time.time()
    # 收集所有候选元素（按钮、链接等）
    selectors = [
        "button",
        "a[role='button']",
        "[role='button']",
        "input[type='submit']",
        "input[type='button']"
    ]
    # 先打印页面上所有可见的按钮文本，方便调试
    all_buttons = page.locator("button, a[role='button'], [role='button']")
    count = all_buttons.count()
    if count > 0:
        log(f"页面上共有 {count} 个可交互元素，显示前20个文本：")
        for i in range(min(count, 20)):
            try:
                text = all_buttons.nth(i).text_content().strip()
                if text:
                    log(f"  {i+1}: {text}")
            except:
                pass

    # 不断尝试匹配（因为页面可能动态加载）
    while (time.time() - start_time) * 1000 < total_timeout:
        # 重新获取元素（避免 stale）
        elements = []
        for sel in selectors:
            elements.extend(page.query_selector_all(sel))
        # 去重（使用元素句柄）
        unique = {}
        for el in elements:
            # 使用元素的内部引用作为 key（避免重复）
            try:
                ref = el._get_pointer()
                if ref not in unique:
                    unique[ref] = el
            except:
                pass
        # 遍历每个元素检查文本
        for el in unique.values():
            try:
                text = el.text_content().strip()
                if not text:
                    continue
                # 检查是否包含任意关键词（忽略大小写）
                text_lower = text.lower()
                for kw in keywords:
                    if kw.lower() in text_lower:
                        log(f"✅ 找到包含关键词 '{kw}' 的按钮：'{text}'")
                        # 确保元素可见且可交互
                        if el.is_visible() and el.is_enabled():
                            el.scroll_into_view_if_needed()
                            time.sleep(0.5)
                            try:
                                el.click()
                                log("✅ 常规点击成功")
                                return True
                            except Exception as e:
                                log(f"常规点击失败，尝试 JavaScript 点击: {e}")
                                page.evaluate("(e) => e.click()", el)
                                log("✅ JavaScript 点击成功")
                                return True
                        else:
                            log(f"元素不可见或不可交互，尝试强制点击")
                            page.evaluate("(e) => e.click()", el)
                            log("✅ JavaScript 强制点击成功")
                            return True
            except Exception as e:
                # 单个元素处理异常，继续下一个
                continue
        # 未找到，等待并重试
        time.sleep(1)
    log(f"❌ 在 {total_timeout}ms 内未找到包含任何关键词的按钮：{keywords}")
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

            # 检查是否已有 token
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

                # 先尝试按 Enter
                log("⏳ 按 Enter 键提交登录...")
                password_input.press("Enter")
                screenshot(page, f"04_after_enter_{account_index}")

                log("⏳ 等待 accessToken 出现...")
                success = wait_for_token(page, timeout=30000)  # 先等待30秒
                if not success:
                    # 如果 Enter 无效，尝试点击登录按钮
                    log("按 Enter 未触发登录，尝试点击登录按钮...")
                    login_btn = page.locator("button:has-text('登录'), button[type='submit'], button:has-text('Sign In'), button:has-text('Login')")
                    if login_btn.count():
                        login_btn.first.click()
                        success = wait_for_token(page, timeout=30000)
                    else:
                        log("未找到登录按钮")
                if not success:
                    screenshot(page, f"05_login_failed_{account_index}")
                    raise RuntimeError(f"账号 {account_index} 登录失败")

            log(f"✅ 账号 {account_index} 登录成功")
            screenshot(page, f"06_logged_in_{account_index}")

            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(3)

            # 1. 点击部署按钮
            log(f"🔍 尝试点击部署按钮，关键词列表：{DEPLOY_KEYWORDS}")
            if not click_button_by_keywords(page, DEPLOY_KEYWORDS, total_timeout=60000):
                screenshot(page, f"07_deploy_failed_{account_index}")
                raise RuntimeError(f"账号 {account_index} 无法点击部署按钮")
            screenshot(page, f"07_deploy_clicked_{account_index}")

            # 等待部署操作完成（判断条件：页面出现某些变化）
            log("⏳ 等待部署操作完成...")
            try:
                # 等待某个成功提示或 URL 变化，这里等待 15 秒确保稳定
                page.wait_for_timeout(15000)
                # 也可以等待网络空闲
                page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            # 2. 点击打开 QwenPaw 按钮
            log(f"🔍 尝试点击 QwenPaw 按钮，关键词列表：{QWEN_KEYWORDS}")
            # 注意：点击后可能打开新窗口或标签页，需要处理
            with context.expect_page() as new_page_info:
                if not click_button_by_keywords(page, QWEN_KEYWORDS, total_timeout=60000):
                    screenshot(page, f"08_qwen_failed_{account_index}")
                    raise RuntimeError(f"账号 {account_index} 无法点击 QwenPaw 按钮")
                # 如果有新页面，等待它加载
                try:
                    new_page = new_page_info.value
                    new_page.wait_for_load_state("networkidle", timeout=10000)
                    log("✅ 新页面（QwenPaw）已加载")
                    screenshot(new_page, f"09_qwen_newpage_{account_index}")
                    new_page.close()
                except Exception as e:
                    # 如果没有新页面，可能是在当前页面打开
                    log(f"未检测到新页面（可能在当前页面打开），等待页面加载...")
                    page.wait_for_load_state("networkidle", timeout=10000)
                    screenshot(page, f"09_qwen_currentpage_{account_index}")

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

    # 收集每个账号的处理结果
    account_results = []
    for idx, cred in enumerate(accounts, start=1):
        username = cred.get("username")
        password = cred.get("password")
        if not username or not password:
            log(f"⚠️ 账号 {idx} 缺少用户名或密码，跳过")
            continue

        start_utc = datetime.now(timezone.utc)
        success = process_account(username, password, idx)
        end_utc = datetime.now(timezone.utc)

        beijing_time = end_utc.astimezone(BEIJING_TZ)
        time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")

        status_text = "✅ 成功" if success else "❌ 失败"
        account_results.append({
            "username": username,
            "time": time_str,
            "status": status_text,
            "success": success
        })
        time.sleep(2)  # 账号之间间隔

    # 统计
    total = len(account_results)
    success_count = sum(1 for r in account_results if r["success"])
    fail_count = total - success_count
    success_rate = (success_count / total * 100) if total > 0 else 0

    # 构建 Telegram 消息
    lines = []
    lines.append("📨 Agentscope 多账号任务报告")
    lines.append("")
    for r in account_results:
        lines.append(f"🖥️ 平台: Agentscope")
        lines.append(f"👤 账号: {r['username']}")
        lines.append(f"⏰ 时间: {r['time']}")
        lines.append(r["status"])
        lines.append("")
    lines.append("📊 统计信息:")
    lines.append(f"✅ 成功: {success_count}/{total}")
    lines.append(f"📈 成功率: {success_rate:.1f}%")
    lines.append("🏁 所有账号操作已完成")
    lines.append("https://platform.agentscope.io")

    message = "\n".join(lines)
    log("📤 发送 Telegram 汇总报告...")
    send_tg(message)

    if fail_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 脚本退出: {e}")
        sys.exit(1)
