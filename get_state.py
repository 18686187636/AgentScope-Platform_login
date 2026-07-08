#!/usr/bin/env python3
"""
首次运行：手动登录 platform.agentscope.io 并导出完整浏览器状态。
增加了等待和验证，确保 LocalStorage 完整。
"""
from playwright.sync_api import sync_playwright
import json
import base64
import time

def main():
    print("启动浏览器，请手动登录 https://platform.agentscope.io/ ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://platform.agentscope.io/")
        print("请在浏览器中完成登录（包括验证码），确保看到 '打开 QwenPaw' 按钮。")
        input("登录成功后，按 Enter 继续...")

        # 等待 5 秒，让 LocalStorage 完全写入
        print("等待 5 秒确保存储持久化...")
        time.sleep(5)

        # 刷新页面，确保存储已持久化
        page.reload()
        time.sleep(2)

        # 验证 LocalStorage 中是否有 refreshToken
        refresh_token = page.evaluate("() => localStorage.getItem('refreshToken')")
        if not refresh_token:
            print("⚠️ 警告：LocalStorage 中未找到 refreshToken，请确认登录成功后再试。")
            retry = input("是否继续导出？(y/n): ")
            if retry.lower() != 'y':
                browser.close()
                return

        # 获取完整状态
        state = context.storage_state()
        # 打印部分信息供检查（不打印敏感值）
        cookies = state.get("cookies", [])
        origins = state.get("origins", [])
        print(f"导出的 Cookie 数量: {len(cookies)}")
        print(f"导出的 Origin 数量: {len(origins)}")
        # 检查是否有 refreshToken
        for origin in origins:
            if "localStorage" in origin:
                for item in origin["localStorage"]:
                    if item["name"] == "refreshToken":
                        print("✅ 检测到 refreshToken 已包含在状态中")
                        break

        state_json = json.dumps(state)
        b64 = base64.b64encode(state_json.encode()).decode()

        print("\n" + "="*60)
        print("请将以下 Base64 字符串完整复制，设置为 GitHub Secret 'AGENTSCOPE_STATE'：")
        print("="*60)
        print(b64)
        print("="*60)

        with open("state_b64.txt", "w") as f:
            f.write(b64)
        print("\n已保存到 state_b64.txt")
        browser.close()

if __name__ == "__main__":
    main()
