# AgentScope-Platform_login
AgentScope Platform每3h检查状态,进行保活
获取 Cookie

[
  {"username": "user1@example.com", "password": "pass1"},
  {"username": "user2@example.com", "password": "pass2"},
  {"username": "user3@example.com", "password": "pass3"}
]

添加 GitHub Secrets

进入仓库 → Settings → Secrets and variables → Actions

点击 New repository secret，分别添加上述变量（名称严格区分大小写）

示例值（仅作参考，请使用实际值）：

ACCOUNTS_JSON 
[
  {"username": "user1@example.com", "password": "pass1"},
  {"username": "user2@example.com", "password": "pass2"},
  {"username": "user3@example.com", "password": "pass3"}
]

TG_BOT_TOKEN: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  #可选

TG_CHAT_ID: 123456789  #可选

注意,多账号处理
[
  {"username": "user1@example.com", "password": "pass1"},
  {"username": "user2@example.com", "password": "pass2"},
  {"username": "user3@example.com", "password": "pass3"}
]
