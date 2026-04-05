import os
import requests
from dotenv import load_dotenv

# [新增原因]: 编写本地脚本，从正式服拉取发送给TUZHAN的反馈邮件，以便进行产品迭代
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, "..", ".env"))

TUZHAN_AGENT_KEY = os.getenv("TUZHAN_AGENT_KEY")
if not TUZHAN_AGENT_KEY:
    print("错误: 未在 .env 中配置 TUZHAN_AGENT_KEY。请确保本地和正式服的密钥一致。")
    exit(1)

# 正式服地址
PROD_URL = "http://118.145.237.44:8888"

def fetch_feedback():
    print(f"正在从正式服 {PROD_URL} 拉取 TUZHAN 的反馈邮件...")
    headers = {"Authorization": f"Bearer {TUZHAN_AGENT_KEY}"}
    
    # 拉取未读邮件
    try:
        resp = requests.get(f"{PROD_URL}/api/messages/receive?status=unread", headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"拉取失败: HTTP {resp.status_code} - {resp.text}")
            return
            
        data = resp.json().get("data", [])
        if not data:
            print("目前没有新的反馈邮件。")
            return
            
        print(f"成功拉取到 {len(data)} 封新反馈邮件！\n")
        
        # 建立反馈保存目录
        feedback_dir = os.path.join(current_dir, "..", "data", "feedbacks")
        os.makedirs(feedback_dir, exist_ok=True)
        
        for msg in data:
            meta = msg.get("metadata", {})
            msg_id = meta.get("id")
            content = msg.get("content", "")
            
            print(f"=== 反馈 [{msg_id}] ===")
            print(f"发件人: {meta.get('sender')} | 时间: {meta.get('timestamp')}")
            print(f"内容:\n{content}\n")
            print("=" * 40 + "\n")
            
            # 将反馈写入本地文件保存，供后续阅读和迭代参考
            filename = os.path.join(feedback_dir, f"feedback_{msg_id}.md")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# 反馈 [{msg_id}]\n\n")
                f.write(f"**发件人:** {meta.get('sender')}\n")
                f.write(f"**时间:** {meta.get('timestamp')}\n\n")
                f.write("---\n\n")
                f.write(content)
                
            print(f"反馈已保存至: {filename}")
            
            # 标记为已读
            ack_resp = requests.post(f"{PROD_URL}/api/messages/{msg_id}/read", headers=headers, timeout=5)
            if ack_resp.status_code == 200:
                print(f"[系统] 邮件 {msg_id} 已在正式服成功标记为已读。")
            else:
                print(f"[系统] 邮件 {msg_id} 标记已读失败。")
                
    except requests.exceptions.RequestException as e:
        print(f"网络请求出错: {e}")

if __name__ == "__main__":
    fetch_feedback()
