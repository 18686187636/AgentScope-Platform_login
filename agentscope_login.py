# .github/workflows/agentscope_login.yml
name: Agentscope Auto Operation

on:
  schedule:
    # 每 3 小时运行一次（UTC 时间）
    - cron: '0 */3 * * *'
  workflow_dispatch:   # 允许手动触发

jobs:
  auto:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install playwright requests
          playwright install --with-deps chromium

      - name: Run login script
        env:
          # 从 GitHub Secret 读取 Base64 编码的完整浏览器状态
          AGENTSCOPE_STATE: ${{ secrets.AGENTSCOPE_STATE }}
          HEADLESS: 'true'
          # 可选：Telegram 通知
          TG_BOT_TOKEN: ${{ secrets.TG_BOT_TOKEN }}
          TG_CHAT_ID: ${{ secrets.TG_CHAT_ID }}
        run: python agentscope_login.py

      - name: Upload debug screenshots (on failure)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: debug-screenshots
          path: |
            *.png
