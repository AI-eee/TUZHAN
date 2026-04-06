import requests
import json
import argparse
import sys
import os
import yaml
from dotenv import load_dotenv

def get_env(override_env=None):
    """如果命令行未指定环境，优先从 .env 读取"""
    if override_env:
        return override_env
    # [修改原因]: 尝试加载 .env 文件，并读取 TUZHAN_ENV
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(current_dir, '..', '..', '.env'))
    return os.getenv("TUZHAN_ENV", "development")

def get_default_url(env="development"):
    """根据环境变量读取配置文件，获取对应的基础URL"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    settings_file = os.path.join(current_dir, '..', '..', 'config', 'settings.yaml')
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = yaml.safe_load(f)
            return settings.get(env, settings["development"]).get("client_base_url", "http://127.0.0.1:8000")
    except Exception:
        return "http://127.0.0.1:8000"

class TuzhanClient:
    """
    轻量级的命令行客户端程序：
    允许任何不在 TUZHAN 仓库（无直接文件读写权限）的人员和 Agent，
    仅通过向服务器发起 HTTP 请求来收发送邮件息。
    """
    
    def __init__(self, base_url=None, env="development"):
        # [修改原因]: 引入环境区分，默认读取 settings.yaml 中的 client_base_url
        self.base_url = base_url if base_url else get_default_url(env)
        print(f"当前客户端请求目标地址: {self.base_url}")

    def send(self, private_key: str, receiver: str, content: str):
        url = f"{self.base_url}/api/messages/send"
        headers = {
            "Authorization": f"Bearer {private_key}"
        }
        payload = {
            "receiver": receiver,
            "content": content
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                print("发送成功:", response.json())
            else:
                print(f"发送失败 [{response.status_code}]:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"请求发送失败: {e}")

    def receive(self, private_key: str):
        url = f"{self.base_url}/api/messages/receive"
        headers = {
            "Authorization": f"Bearer {private_key}"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get("data", [])
                print(f"\n--- 收件箱 (共 {len(data)} 封邮件) ---")
                for msg in data:
                    meta = msg.get("metadata", {})
                    msg_id = meta.get("id")
                    print(f"\n[{meta.get('timestamp')}] {meta.get('sender')} -> 你")
                    print(f"状态: {meta.get('status')}")
                    print(f"内容:\n{msg.get('content')}")
                    print("-" * 40)
                    
                    # [修改原因]: API客户端读取收件箱后，自动将邮件标记为已读，避免后续堆积和重复处理
                    if meta.get("status") == "unread" and msg_id:
                        ack_url = f"{self.base_url}/api/messages/{msg_id}/read"
                        ack_resp = requests.post(ack_url, headers=headers)
                        if ack_resp.status_code == 200:
                            print(f"[系统] 邮件 {msg_id} 已标记为已读")
                        else:
                            print(f"[系统] 邮件 {msg_id} 标记已读失败")
            else:
                print(f"读取失败 [{response.status_code}]:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"请求接收失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="TUZHAN Agent协作中心客户端 (API 封装)")
    parser.add_argument("--url", help="API 服务器地址 (如果不填，将从 settings.yaml 根据环境读取)")
    subparsers = parser.add_subparsers(dest="command", help="可用命令: send, receive")

    # send 子命令
    send_parser = subparsers.add_parser("send", help="发送邮件")
    send_parser.add_argument("--key", required=True, help="你的 Private Key (身份凭证)")
    send_parser.add_argument("--receiver", required=True, help="接收方")
    send_parser.add_argument("--content", required=True, help="邮件正文内容 (支持 Markdown 语法)")

    # receive 子命令
    receive_parser = subparsers.add_parser("receive", help="查看收件箱")
    receive_parser.add_argument("--key", required=True, help="你的 Private Key (身份凭证)")

    # 增加 --env 参数用于切换请求的环境
    parser.add_argument("--env", choices=["development", "production"], default=None, help="运行环境 (默认从 .env 读取)")

    args = parser.parse_args()

    # 解析环境
    env = get_env(args.env if hasattr(args, 'env') else None)
    client = TuzhanClient(base_url=args.url, env=env)

    if args.command == "send":
        client.send(args.key, args.receiver, args.content)
    elif args.command == "receive":
        client.receive(args.key)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
