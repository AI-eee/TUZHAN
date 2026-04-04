import os
import sys
import unittest
import requests
import json
from dotenv import load_dotenv

# Add src to sys.path to import internal modules for data setup
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.database import DatabaseManager

class TestAgentMessaging(unittest.TestCase):
    BASE_URL = "http://localhost:8888/api"
    
    @classmethod
    def setUpClass(cls):
        """
        初始化测试所需的数据（如果数据库数据不全）
        [修改原因]: 确保测试环境具备运行所需的项目、成员及密钥，保证每次跑都能完整验证。
        """
        # 加载环境变量获取环境配置
        load_dotenv(os.path.join(project_root, ".env"))
        
        # 获取数据库路径（默认开发库）
        env = os.getenv("TUZHAN_ENV", "development")
        config_path = os.path.join(project_root, "config.yml")
        db_path = os.path.join(project_root, "data", "dev.sqlite")
        
        if os.path.exists(config_path):
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
                db_url = settings.get(env, settings.get("development", {})).get("database_url", "")
                if db_url.startswith("sqlite:///./"):
                    db_path = os.path.abspath(os.path.join(project_root, db_url[11:]))
                elif db_url.startswith("sqlite:///"):
                    db_path = os.path.abspath(db_url[10:])

        cls.db = DatabaseManager(db_path)
        cls.db.init_tables()
        
        # 准备测试数据
        cls.sender_emp_id = "test_agent_s1"
        cls.sender_key = "sk-test-sender-key"
        cls.receiver_emp_id = "test_agent_r1"
        cls.receiver_key = "sk-test-receiver-key"
        cls.project_name = "Test_Agent_Project"
        
        # 1. 确保用户存在
        cls.db.ensure_user_exists(cls.sender_emp_id, "Agent Sender", "[]", cls.sender_key)
        cls.db.ensure_user_exists(cls.receiver_emp_id, "Agent Receiver", "[]", cls.receiver_key)
        
        # 2. 确保项目存在
        cls.db.add_project(cls.project_name, "项目用于Agent收发信息测试")
        
        # 3. 将用户加入项目，使他们可以通信
        # (因为规则限制：只有同属一个项目的成员才能通信，或者说只有有项目的成员才能拉取列表和发信)
        cls.db.add_project_member(cls.project_name, cls.sender_emp_id, "Bot")
        cls.db.add_project_member(cls.project_name, cls.receiver_emp_id, "Bot")
        
        # 4. 同步项目信息到用户的 projects 字段 (解决API层面的限制)
        cls.db.sync_projects_to_users_json()

    def test_1_get_projects(self):
        """测试 Agent 是否能正常获取项目和成员列表"""
        headers = {"Authorization": f"Bearer {self.sender_key}"}
        resp = requests.get(f"{self.BASE_URL}/projects", headers=headers)
        
        self.assertEqual(resp.status_code, 200, f"获取项目列表失败: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        
        projects = data.get("data", [])
        project_names = [p.get("name") for p in projects]
        self.assertIn(self.project_name, project_names, "Agent 未能拉取到测试项目")
        
        # 检查能否看到接收者
        test_proj = next(p for p in projects if p["name"] == self.project_name)
        member_ids = [m.get("emp_id") for m in test_proj.get("members", [])]
        self.assertIn(self.receiver_emp_id, member_ids, "项目中缺少接收者")

    def test_2_send_message(self):
        """测试 Agent 发送信息功能"""
        headers = {"Authorization": f"Bearer {self.sender_key}"}
        payload = {
            "receiver": self.receiver_emp_id,
            "content": "# Test Message\\n\\nThis is an automated test message from Agent."
        }
        resp = requests.post(f"{self.BASE_URL}/messages/send", headers=headers, json=payload)
        
        self.assertEqual(resp.status_code, 200, f"发送信息失败: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("status"), "success")

    def test_3_receive_message(self):
        """测试 Agent 接收信息功能"""
        headers = {"Authorization": f"Bearer {self.receiver_key}"}
        resp = requests.get(f"{self.BASE_URL}/messages/receive", headers=headers)
        
        self.assertEqual(resp.status_code, 200, f"接收信息失败: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        
        messages = data.get("data", [])
        self.assertTrue(len(messages) > 0, "收件箱为空")
        
        # 验证最新的一条消息是否来自 sender
        latest_msg = messages[0]
        self.assertEqual(latest_msg["metadata"]["sender"], self.sender_emp_id, "发送者不匹配")
        self.assertIn("Test Message", latest_msg["content"], "消息内容不匹配")

if __name__ == "__main__":
    unittest.main()
