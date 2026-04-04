import os
import sys
import urllib.request
import urllib.error
import json

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

def main():
    if not API_KEY:
        print("错误: 未配置 API_KEY！")
        print("请在脚本中直接修改 API_KEY，或者通过环境变量 TUZHAN_API_KEY 传入。")
        print("示例: export TUZHAN_API_KEY='sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'")
        sys.exit(1)

    print(f"正在使用工作区: {WORKSPACE_DIR}")
    print("1. 获取全公司项目和同事名单 (/projects) ...")
    projects = request("/projects")
    if not projects or projects.get("status") != "success":
        print("获取失败，请检查 API Key 或网络连通性。")
        return
        
    print("获取成功。")
    
    target_emp_id = None
    if projects.get("data"):
        for proj in projects["data"]:
            if proj.get("members"):
                target_emp_id = proj["members"][0]["emp_id"]
                break
                
    if target_emp_id:
        # print(f"\n2. 发送测试消息给 {target_emp_id} (/messages/send) ...")
        # send_payload = json.dumps({
        #     "receiver": target_emp_id,
        #     "content": "# 测试消息\n\n这是一条通过 Python 脚本自动发送的 API 测试消息。"
        # }).encode("utf-8")
        # send_res = request("/messages/send", method="POST", data=send_payload)
        # print("发送成功。" if send_res and send_res.get("status") == "success" else "发送失败。")
        pass
    else:
        print("\n未找到任何同事。")

    inbox_dir = os.path.join(WORKSPACE_DIR, "inbox")
    outbox_dir = os.path.join(WORKSPACE_DIR, "outbox")
    
    # 创建收件箱和发件箱文件夹
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(outbox_dir, exist_ok=True)

    print(f"\n3. 检查发件箱 (/messages/sent) 并保存到本地 {outbox_dir} ...")
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
        print(f"已将 {count} 条新的发件箱消息保存到 {outbox_dir}")
    else:
        print("拉取发件箱失败")
    
    print(f"\n4. 检查收件箱 (/messages/receive) 并保存到本地 {inbox_dir} ...")
    received = request("/messages/receive")
    if received and received.get("status") == "success":
        count = 0
        for msg in received.get("data", []):
            sender_id = msg.get("metadata", {}).get("sender", "unknown")
            emp_inbox_dir = os.path.join(inbox_dir, sender_id)
            os.makedirs(emp_inbox_dir, exist_ok=True)
            
            filepath = os.path.join(emp_inbox_dir, msg["filename"])
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(msg["content"])
                count += 1
        print(f"已将 {count} 条新的收件箱消息保存到 {inbox_dir}")
    else:
        print("拉取收件箱失败")

if __name__ == "__main__":
    main()
