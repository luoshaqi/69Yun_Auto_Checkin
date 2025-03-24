import os
import json
import requests
import time
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 解析用户信息
def fetch_and_extract_info(domain, headers):
    url = f"{domain}/user"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return "❌ 用户信息获取失败\n"

    soup = BeautifulSoup(response.text, 'html.parser')
    script_tags = soup.find_all('script')

    chatra_script = next((script.string for script in script_tags if script.string and 'window.ChatraIntegration' in script.string), None)
    if not chatra_script:
        return "⚠️ 未识别到用户信息\n"

    user_info = {
        '到期时间': re.search(r"'Class_Expire': '(.*?)'", chatra_script),
        '剩余流量': re.search(r"'Unused_Traffic': '(.*?)'", chatra_script)
    }
    for key in user_info:
        user_info[key] = user_info[key].group(1) if user_info[key] else "未知"

    # 提取 Clash 和 v2ray 订阅链接
    link_match = next((re.search(r"'https://checkhere.top/link/(.*?)\?sub=1'", str(script))
                       for script in script_tags if 'index.oneclickImport' in str(script) and 'clash' in str(script)), None)
    sub_links = ""
    if link_match:
        sub_links = (
            f"<br><b>Clash 订阅</b>: <a href='https://checkhere.top/link/{link_match.group(1)}?clash=1'>点击订阅</a>"
            f"<br><b>V2ray 订阅</b>: <a href='https://checkhere.top/link/{link_match.group(1)}?sub=3'>点击订阅</a>"
        )

    return (
        f"<b>到期时间</b>: {user_info['到期时间']}<br>"
        f"<b>剩余流量</b>: {user_info['剩余流量']}{sub_links}<br>"
    )

# 读取环境变量并生成配置
def generate_config():
    domain = os.getenv('DOMAIN', 'https://69yun69.com')
    bot_token = os.getenv('BOT_TOKEN', '')
    chat_id = os.getenv('CHAT_ID', '')
    
    accounts = []
    index = 1
    while True:
        user, password = os.getenv(f'USER{index}'), os.getenv(f'PASS{index}')
        if not user or not password:
            break
        accounts.append({'user': user, 'pass': password})
        index += 1

    return {'domain': domain, 'BotToken': bot_token, 'CHATID': chat_id, 'accounts': accounts}

# 发送 Telegram 消息（HTML 格式）
def send_message(msg, bot_token, chat_id):
    now = datetime.utcnow() + timedelta(hours=8)  # 北京时间
    payload = {
        "chat_id": chat_id,
        "text": f"<b>执行时间</b>: {now.strftime('%Y-%m-%d %H:%M:%S')}<br><br>{msg}",
        "parse_mode": "HTML"
    }
    try:
        # 使用 json=payload 而不是 data=payload
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload)
    except Exception as e:
        print("❌ 发送 Telegram 消息失败：", e)

# 登录并签到
def checkin(account, domain, bot_token, chat_id):
    user, password = account['user'], account['pass']
    info = (
        f"<b>地址</b>: {domain}<br>"
        f"<b>账号</b>: {user}<br>"
        f"<b>密码</b>: {password}<br>"
    )

    # 登录请求
    login_response = requests.post(
        f"{domain}/auth/login",
        json={'email': user, 'passwd': password, 'remember_me': 'on', 'code': ""},
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': domain,
            'Referer': f"{domain}/auth/login",
        }
    )

    try:
        login_ret = login_response.json()
    except Exception:
        login_ret = {}
    if login_response.status_code != 200 or login_ret.get("ret") != 1:
        err_msg = f"❌ 登录失败: {login_ret.get('msg', '未知错误')}"
        send_message(info + err_msg, bot_token, chat_id)
        return err_msg

    cookies = login_response.cookies
    time.sleep(1)

    # 签到请求
    checkin_response = requests.post(
        f"{domain}/user/checkin",
        headers={
            'Cookie': '; '.join([f"{key}={value}" for key, value in cookies.items()]),
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': domain,
            'Referer': f"{domain}/user/panel"
        }
    )
    try:
        checkin_ret = checkin_response.json() if checkin_response.status_code == 200 else {}
    except Exception:
        checkin_ret = {}

    result_msg = checkin_ret.get('msg', '签到结果未知')
    result_emoji = "✅" if checkin_ret.get('ret') == 1 else "⚠️"

    user_info = fetch_and_extract_info(domain, {
        'Cookie': '; '.join([f"{key}={value}" for key, value in cookies.items()])
    })

    final_msg = (
        f"{info}<br>"
        f"{user_info}<br>"
        f"<b>签到结果</b>: {result_emoji} {result_msg}"
    )
    send_message(final_msg, bot_token, chat_id)
    return final_msg

# 主函数（不在日志中输出敏感信息）
if __name__ == "__main__":
    config = generate_config()
    for account in config.get("accounts", []):
        print("📌 正在执行签到任务...")
        checkin(account, config['domain'], config['BotToken'], config['CHATID'])