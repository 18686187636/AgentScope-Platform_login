# agentscope_login.py
import os, sys, json, base64, time, requests
from playwright.sync_api import sync_playwright
from datetime import datetime

STATE_B64 = os.getenv("AGENTSCOPE_STATE", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")
REFRESH_URL = "https://platform.agentscope.io/api/v1/auth/refresh"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            log(f"Telegram 发送失败: {e}")

def get_cookie_from_state(state, name="qwenpaw_console_token"):
    for c in state.get("cookies", []):
        if c.get("name") == name:
            return c.get("value")
    return None

def get_local_storage_item(state, key):
    """从 state 的 origins 中提取 localStorage 指定键的值"""
    for origin in state.get("origins", []):
        for item in origin.get("localStorage", []):
            if item.get("name") == key:
                return item.get("value")
    return None

def refresh_token(refresh_token_str, cookie_value):
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"qwenpaw_console_token={cookie_value}",
        "Origin": "https://platform.agentscope.io",
        "Referer": "https://platform.agentscope.io/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    }
    payload = {"refreshToken": refresh_token_str}
    try:
        resp = requests.post(REFRESH_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("accessToken") or data.get("access_token") or data.get("token")
            expires = data.get("expiresIn") or data.get("expires_in") or 3600
            if new_token:
                return new_token, expires
            else:
                raise Exception(f"响应中无 token 字段: {data}")
        else:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        raise Exception(f"刷新请求失败: {e}")

def run():
    if not STATE_B64:
        log("❌ 缺少 AGENTSCOPE_STATE")
        sys.exit(1)

    try:
        state_json = base64.b64decode(STATE_B64).decode()
        state = json.loads(state_json)
    except Exception as e:
        log(f"❌ 解码失败: {e}")
        sys.exit(1)

    # 诊断：打印状态概要
    log(f"状态中 Cookie 数量: {len(state.get('cookies', []))}")
    log(f"状态中 Origins 数量: {len(state.get('origins', []))}")
    # 检查 refreshToken 是否存在
    refresh_in_state = get_local_storage_item(state, "refreshToken")
    if refresh_in_state:
        log("✅ 状态中包含 refreshToken")
    else:
        log("⚠️ 状态中未找到 refreshToken")

    cookie_value = get_cookie_from_state(state)
    if cookie_value:
        log("✅ 找到 qwenpaw_console_token")
    else:
        log("⚠️ 未找到 qwenpaw_console_token")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(storage_state=state)
        page = context.new_page()
        log("🌐 访问平台...")
        page.goto("https://platform.agentscope.io/", wait_until="domcontentloaded")
        time.sleep(3)

        # 检查登录状态
        login_btn = page.locator("button:has-text('登录')")
        if login_btn.count() and login_btn.is_visible():
            log("⚠️ 检测到登录按钮，尝试刷新 token...")
            # 优先从 page 的 localStorage 获取 refreshToken
            refresh = page.evaluate("() => localStorage.getItem('refreshToken')")
            if not refresh:
                # 如果页面中没有，尝试从 state 中获取（可能加载时未正确写入）
                refresh = get_local_storage_item(state, "refreshToken")
                if refresh:
                    log("从 state 中提取到 refreshToken，尝试写入页面...")
                    page.evaluate(f"window.localStorage.setItem('refreshToken', '{refresh}')")
                    # 重新加载页面
                    page.reload()
                    time.sleep(2)
                    refresh = page.evaluate("() => localStorage.getItem('refreshToken')")
            if not refresh:
                raise Exception("本地没有 refreshToken，请重新导出状态（确保登录后等待几秒再导出）")
            if not cookie_value:
                raise Exception("没有 qwenpaw_console_token，请重新导出状态")

            try:
                new_token, expires = refresh_token(refresh, cookie_value)
                page.evaluate(f"window.localStorage.setItem('accessToken', '{new_token}')")
                page.evaluate(f"window.localStorage.setItem('expiresIn', '{expires}')")
                log(f"✅ Token 刷新成功，有效期 {expires} 秒")
                page.reload()
                time.sleep(2)
                if page.locator("button:has-text('登录')").count():
                    raise Exception("刷新后仍显示登录按钮")
                log("✅ 刷新后登录成功")
            except Exception as e:
                send_tg(f"❌ Agentscope 自动刷新失败\n错误: {e}")
                raise
        else:
            log("✅ 已登录")

        # 点击按钮
        for text in ["打开 QwenPaw", "QwenPaw", "Launch QwenPaw"]:
            btn = page.locator(f"button:has-text('{text}'), a:has-text('{text}')")
            if btn.count():
                btn.first.click()
                log(f"✅ 点击 '{text}' 成功")
                break
        else:
            raise Exception("未找到目标按钮")

        log("🎉 脚本执行完毕")
        send_tg("✅ Agentscope 自动操作成功")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log(f"❌ 执行失败: {e}")
        send_tg(f"❌ Agentscope 脚本失败: {e}")
        sys.exit(1)
