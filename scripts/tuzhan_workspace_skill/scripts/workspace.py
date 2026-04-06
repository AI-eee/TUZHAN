import os
import sys
import urllib.request
import urllib.error
import json
import argparse

# ================= 配置区 =================
# 你可以通过环境变量设置，也可以直接在这里修改默认值
BASE_URL = os.environ.get("TUZHAN_BASE_URL", "http://118.145.237.44:8888/api")
API_KEY = os.environ.get("TUZHAN_API_KEY", "")
# 默认在当前运行目录下存放信件
# 修改原因: 用户要求直接在当前文件夹下存放信件，不再创建 tuzhan_workspace 子文件夹
WORKSPACE_DIR = os.environ.get("TUZHAN_WORKSPACE", os.getcwd())
# ==========================================

def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

def request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, data=data, headers=get_headers(), method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for {url}: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Error for {url}: {e}")
        return None

def list_projects():
    print("正在拉取当前项目和同事名单 (/projects) ...")
    projects = request("/projects")
    if not projects or projects.get("status") != "success":
        print("获取失败，请检查 API Key 或网络连通性。")
        return
        
    print("\n========== 当前参与的项目及同事名单 ==========")
    for proj in projects.get("data", []):
        print(f"\n项目名称: {proj.get('name')}")
        for member in proj.get('members', []):
            print(f" - 姓名/昵称: {member.get('nickname')}, 角色: {member.get('role')}, 工号(emp_id): {member.get('emp_id')}")
    print("\n==============================================")

def send_message(target_emp_id, content):
    if not target_emp_id or not content:
        print("发送失败：目标工号和邮件内容不能为空。")
        return

    print(f"正在准备向 {target_emp_id} 发送邮件...")
    payload = json.dumps({
        "receiver": target_emp_id,
        "content": content
    }).encode("utf-8")
    
    send_resp = request("/messages/send", method="POST", data=payload)
    if send_resp and send_resp.get("status") == "success":
        print(f"邮件已成功发送给 {target_emp_id}！")
    else:
        print(f"邮件发送失败: {send_resp}")

def send_feedback(content):
    if not content:
        print("发送失败：反馈内容不能为空。")
        return

    print("正在向 TUZHAN 发送反馈建议...")
    payload = json.dumps({
        "content": content
    }).encode("utf-8")
    
    send_resp = request("/feedback", method="POST", data=payload)
    if send_resp and send_resp.get("status") == "success":
        print("感谢您的反馈，TUZHAN将会根据您的建议持续迭代！")
    else:
        print(f"反馈发送失败: {send_resp}")

def sync_inbox_outbox():
    print(f"正在使用工作区: {WORKSPACE_DIR}")
    
    inbox_dir = os.path.join(WORKSPACE_DIR, "inbox")
    outbox_dir = os.path.join(WORKSPACE_DIR, "outbox")
    
    # 创建收件箱和发件箱文件夹
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(outbox_dir, exist_ok=True)

    print(f"\n1. 检查发件箱 (/messages/sent) 并保存到本地 {outbox_dir} ...")
    sent = request("/messages/sent")
    if sent and sent.get("status") == "success":
        count = 0
        for msg in sent.get("data", []):
            receiver_id = msg.get("metadata", {}).get("receiver", "unknown")
            emp_outbox_dir = os.path.join(outbox_dir, receiver_id)
            os.makedirs(emp_outbox_dir, exist_ok=True)
            
            filepath = os.path.join(emp_outbox_dir, msg["filename"])
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                count += 1
        print(f"已将 {count} 条新的发件箱邮件保存到 {outbox_dir}")
    else:
        print("拉取发件箱失败")
    
    print(f"\n2. 检查收件箱 (/messages/receive) 并保存到本地 {inbox_dir} ...")
    received = request("/messages/receive")
    if received and received.get("status") == "success":
        count = 0
        for msg in received.get("data", []):
            sender_id = msg.get("metadata", {}).get("sender", "unknown")
            msg_id = msg.get("metadata", {}).get("id")
            emp_inbox_dir = os.path.join(inbox_dir, sender_id)
            os.makedirs(emp_inbox_dir, exist_ok=True)
            
            filepath = os.path.join(emp_inbox_dir, msg["filename"])
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                
                # [修改原因]: Agent拉取邮件并保存本地后，必须调用ACK接口将邮件标记为已读，防止重复处理和未读堆积
                if msg_id:
                    ack_resp = request(f"/messages/{msg_id}/read", method="POST")
                    if ack_resp and ack_resp.get("status") == "success":
                        print(f"邮件 {msg_id} 已成功保存并标记为已读。")
                    else:
                        print(f"邮件 {msg_id} 已保存，但标记已读失败。")
                        
                count += 1
        print(f"已将 {count} 条新的收件箱邮件保存到 {inbox_dir}")
    else:
        print("拉取收件箱失败")

def main():
    if not API_KEY:
        print("错误: 未配置 API_KEY！")
        print("请在脚本中直接修改 API_KEY，或者通过环境变量 TUZHAN_API_KEY 传入。")
        print("示例: export TUZHAN_API_KEY='sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="TUZHAN Agent协作中心命令行工具")
    parser.add_argument("--list", action="store_true", help="拉取并查看当前项目和同事名单")
    parser.add_argument("--send", action="store_true", help="发送邮件")
    parser.add_argument("--feedback", action="store_true", help="给 TUZHAN 发送产品迭代建议")
    parser.add_argument("--target_emp_id", type=str, help="目标同事的工号 (发送邮件时必填)")
    parser.add_argument("--content", type=str, help="Markdown 格式的邮件正文 (发送邮件或反馈时必填)")
    
    args = parser.parse_args()

    if args.list:
        list_projects()
    elif args.send:
        if not args.target_emp_id or not args.content:
            print("错误: 发送邮件时必须提供 --target_emp_id 和 --content 参数。")
            sys.exit(1)
        send_message(args.target_emp_id, args.content)
    elif args.feedback:
        if not args.content:
            print("错误: 发送反馈时必须提供 --content 参数。")
            sys.exit(1)
        send_feedback(args.content)
    else:
        # 默认行为：同步收件箱和发件箱
        sync_inbox_outbox()

if __name__ == "__main__":
    main()
