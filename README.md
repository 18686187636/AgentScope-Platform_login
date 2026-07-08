# AgentScope-Platform_login
AgentScope Platform每3h检查状态,进行保活
获取 Cookie
首次本地运行登录脚本 get_state.py  会弹出浏览器,需要手动登录一次,登录后点击 一键部署 ,看到新页面的   打开确保看到 '打开 QwenPaw' 按钮,回到此终端按 Enter 键继续.复制python目录下复制state_b64.txt里面的代码填入github的加密变量  AGENTSCOPE_STATE

添加 GitHub Secrets

进入仓库 → Settings → Secrets and variables → Actions

点击 New repository secret，分别添加上述变量（名称严格区分大小写）

示例值（仅作参考，请使用实际值）：
AGENTSCOPE_STATE  #state_b64.txt里面的值  #必须填写

TG_BOT_TOKEN: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  #可选

TG_CHAT_ID: 123456789  #可选
注意
只有首次需要本地运行获取state_b64.txt的值,后续无需再运行,除非TG bot 通知登录失败 ,假如登录失败,需要手动更新AGENTSCOPE_STATE变量

