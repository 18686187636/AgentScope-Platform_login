# AgentScope-Platform_login
AgentScope Platform每3h检查状态,进行保活

#### 2. 设置 GitHub Secrets

1. **创建 Telegram Bot**
    - 在 Telegram 中找到 `@BotFather`，创建一个新 Bot，并获取 API Token。
    
2. **配置 GitHub Secrets**
    - 转到你 fork 的仓库页面。
    - 点击 `Settings`，然后在左侧菜单中选择 `Secrets`。
    - 添加以下 Secrets：
        - `ACCOUNTS_JSON`: 包含账号信息的 JSON 数据。例如：
        - 
          ```json
          [
            {"username": "user1@example.com", "password": "pass1"},
            {"username": "user2@example.com", "password": "pass2"},
            {"username": "user3@example.com", "password": "pass3"}
          ]
          ```
        - `TELEGRAM_BOT_TOKEN`: 你的 Telegram Bot 的 API Token。
        - `TELEGRAM_CHAT_ID`: 你的 Telegram Chat ID。
        
    - **获取方法**：
        - 在 Telegram 中创建 Bot，并获取 API Token 和 Chat ID。
        - 在 GitHub 仓库的 Secrets 页面添加这些值，确保它们安全且不被泄露。
示例值（仅作参考，请使用实际值）：

      ACCOUNTS_JSON
     - 
          ```json
          [
            {"username": "user1@example.com", "password": "pass1"},
            {"username": "user2@example.com", "password": "pass2"},
            {"username": "user3@example.com", "password": "pass3"}
          ]
          ```
      
TG_BOT_TOKEN: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  #可选

TG_CHAT_ID: 123456789  #可选
 
注意,多账号处理:
 
   ACCOUNTS_JSON
   -  -
         ```json
          [
            {"username": "user1@example.com", "password": "pass1"},
            {"username": "user2@example.com", "password": "pass2"},
            {"username": "user3@example.com", "password": "pass3"}
          ]
          ```
          
json中username就是用户名,也就是邮箱,password也就是密码
