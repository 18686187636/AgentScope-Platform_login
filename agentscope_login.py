# agentscope_login.py
import os, sys, json, base64, time, requests
from playwright.sync_api import sync_playwright
from datetime import datetime

STATE_B64 = os.getenv("AGENTSCOPE_STATE", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")

# 从抓包信息中确定的正确刷新接口
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

def refresh_token(refresh_token_str, cookie_value):
    """
    调用正确的刷新接口
    - refresh_token_str: refreshToken 的值
    - cookie_value: qwenpaw_console_token 的值（从浏览器 Cookie 中获取）
    """
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
        log(f"刷新接口响应状态: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # 根据实际响应格式调整字段名（常见可能是 accessToken 或 access_token）
            new_token = data.get("accessToken") or data.get("access_token") or data.get("token")
            expires = data.get("expiresIn") or data.get("expires_in") or 3600
            if new_token:
                return new_token, expires
            else:
                log(f"响应中未找到 token，完整响应: {data}")
                raise Exception("刷新响应中无 token 字段")
        else:
            raise Exception(f"刷新失败 HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        raise Exception(f"刷新请求异常: {e}")

def get_cookie_from_state(state):
    """从 state 中提取 qwenpaw_console_token"""
    cookies = state.get("cookies", [])
    for c in cookies:
        if c.get("name") == "qwenpaw_console_token":
            return c.get("value")
    return None

def run():
    if not STATE_B64:
        log("❌ 缺少 AGENTSCOPE_STATE，请在 GitHub Secret 中设置")
        sys.exit(1)
    try:
        state_json = base64.b64decode(STATE_B64).decode()
        state = json.loads(state_json)
    except Exception as e:
        log(f"❌ 解码状态失败: {e}")
        sys.exit(1)

    # 提取 Cookie（刷新时需要）
    cookie_value = get_cookie_from_state(state)
    if not cookie_value:
        log("⚠️ 未找到 qwenpaw_console_token，刷新可能失败")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context(storage_state=state)
        page = context.new_page()
        log("🌐 访问平台...")
        page.goto("https://platform.agentscope.io/", wait_until="domcontentloaded")
        time.sleep(2)

        # 检查是否已登录（是否存在“登录”按钮）
        login_btn = page.locator("button:has-text('登录')")
        if login_btn.count() and login_btn.is_visible():
            log("⚠️ 检测到登录按钮，尝试刷新 token...")
            # 从 localStorage 获取 refreshToken
            refresh = page.evaluate("() => localStorage.getItem('refreshToken')")
            if not refresh:
                raise Exception("本地没有 refreshToken，请重新导出状态")
            if not cookie_value:
                raise Exception("没有 qwenpaw_console_token，无法刷新")
            try:
                new_token, expires = refresh_token(refresh, cookie_value)
                # 更新 localStorage
                page.evaluate(f"window.localStorage.setItem('accessToken', '{new_token}')")
                page.evaluate(f"window.localStorage.setItem('expiresIn', '{expires}')")
                log(f"✅ token 刷新成功，有效期 {expires} 秒")
                page.reload()
                time.sleep(2)
                # 再次检查登录状态
                if page.locator("button:has-text('登录')").count():
                    raise Exception("刷新后仍显示登录按钮，可能 refreshToken 无效")
                log("✅ 刷新后登录成功")
            except Exception as e:
                send_tg(f"❌ Agentscope 自动刷新失败\n错误: {e}")
                raise
        else:
            log("✅ 已登录")

        # 点击目标按钮
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
