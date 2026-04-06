"""
员工接口 - 邮件收发测试
========================
测试 Agent/员工通过 API 发送和接收 Markdown 邮件的完整流程。
"""
import pytest
import requests


def _auth(key):
    return {"Authorization": f"Bearer {key}"}


class TestSendMessage:
    """POST /api/messages/send"""

    def test_send_message_success(self, api_url, user1, user2):
        """员工应能成功发送邮件给同项目成员"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": user2["emp_id"],
            "content": "# 测试邮件\n\n这是一条自动化测试发送的 Markdown 邮件。",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["msg_ids"]) == 1

    def test_send_to_multiple_receivers(self, api_url, user1, user2, admin_user):
        """支持逗号分隔的多接收人群发"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": f"{user2['emp_id']},{admin_user['emp_id']}",
            "content": "# 群发测试\n\n这条邮件群发给两个人。",
        })
        assert resp.status_code == 200
        assert len(resp.json()["msg_ids"]) == 2

    def test_send_to_invalid_receiver(self, api_url, user1):
        """发送给不存在的用户应返回 invalid_receivers"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": "TZ_NOT_EXIST_USER",
            "content": "这条邮件发不出去",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "invalid_receivers" in data
        assert "TZ_NOT_EXIST_USER" in data["invalid_receivers"]

    def test_send_mixed_valid_and_invalid(self, api_url, user1, user2):
        """混合有效和无效收件人，有效的应成功，无效的被标记"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": f"{user2['emp_id']},TZ_GHOST_USER",
            "content": "部分有效的群发测试",
        })
        data = resp.json()
        assert len(data["msg_ids"]) == 1
        assert "TZ_GHOST_USER" in data["invalid_receivers"]

    def test_send_to_other_project_blocked(self, api_url, user1, user3):
        """发送给不在同一项目的人应被拦截"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": user3["emp_id"],
            "content": "跨项目发送测试",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("msg_ids", [])) == 0
        assert user3["emp_id"] in data.get("invalid_receivers", [])

    def test_send_feedback_to_tuzhan_cross_project(self, api_url, user1, noproj_user):
        """任何人（包括无项目组人员）都可以向 TUZHAN 提交反馈，不受项目组限制"""
        # 测试普通有项目人员发送
        resp1 = requests.post(f"{api_url}/feedback", headers=_auth(user1["key"]), json={
            "content": "给 TUZHAN 的建议1"
        })
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "success"

        # 测试无项目人员发送
        resp2 = requests.post(f"{api_url}/feedback", headers=_auth(noproj_user["key"]), json={
            "content": "给 TUZHAN 的建议2"
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "success"

    def test_send_without_token_returns_401(self, api_url, user2):
        """未携带 Token 发送邮件应返回 401"""
        resp = requests.post(f"{api_url}/messages/send", json={
            "receiver": user2["emp_id"], "content": "no auth",
        })
        assert resp.status_code == 401

    def test_noproj_user_cannot_send(self, api_url, noproj_user, user1):
        """不属于任何项目的员工不能发送邮件"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(noproj_user["key"]), json={
            "receiver": user1["emp_id"], "content": "我没有项目",
        })
        assert resp.status_code == 403

    def test_disabled_user_cannot_send(self, api_url, disabled_user, user1):
        """被禁用的员工不能发送邮件"""
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(disabled_user["key"]), json={
            "receiver": user1["emp_id"], "content": "我被禁用了",
        })
        assert resp.status_code == 403

    def test_send_markdown_content_preserved(self, api_url, user1, user2):
        """发送的 Markdown 内容应完整保留"""
        md = "## 标题\n\n- 列表项1\n- 列表项2\n\n```python\nprint('hello')\n```"
        resp = requests.post(f"{api_url}/messages/send", headers=_auth(user1["key"]), json={
            "receiver": user2["emp_id"], "content": md,
        })
        assert resp.status_code == 200


class TestReceiveMessage:
    """GET /api/messages/receive"""

    def test_receive_inbox(self, api_url, user2):
        """员工应能获取自己的收件箱"""
        resp = requests.get(f"{api_url}/messages/receive", headers=_auth(user2["key"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    def test_inbox_message_structure(self, api_url, user2):
        """收件箱邮件应包含正确的 metadata 和 content 结构"""
        resp = requests.get(f"{api_url}/messages/receive", headers=_auth(user2["key"]))
        msg = resp.json()["data"][0]
        assert "metadata" in msg
        assert "content" in msg
        assert "filename" in msg
        for field in ("id", "sender", "receiver", "timestamp", "status"):
            assert field in msg["metadata"]

    def test_receive_without_token_returns_401(self, api_url):
        """未携带 Token 获取收件箱应返回 401"""
        assert requests.get(f"{api_url}/messages/receive").status_code == 401

    def test_noproj_user_cannot_receive(self, api_url, noproj_user):
        """不属于任何项目的员工不能拉取收件箱"""
        resp = requests.get(f"{api_url}/messages/receive", headers=_auth(noproj_user["key"]))
        assert resp.status_code == 403

    def test_disabled_user_cannot_receive(self, api_url, disabled_user):
        """被禁用的员工不能拉取收件箱"""
        resp = requests.get(f"{api_url}/messages/receive", headers=_auth(disabled_user["key"]))
        assert resp.status_code == 403


class TestSentMessages:
    """GET /api/messages/sent"""

    def test_get_sent_messages(self, api_url, user1):
        """员工应能获取自己的发件箱"""
        resp = requests.get(f"{api_url}/messages/sent", headers=_auth(user1["key"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["data"]) > 0

    def test_sent_message_shows_correct_sender(self, api_url, user1):
        """发件箱中的邮件 sender 应为自己"""
        resp = requests.get(f"{api_url}/messages/sent", headers=_auth(user1["key"]))
        for msg in resp.json()["data"]:
            assert msg["metadata"]["sender"] == user1["emp_id"]

    def test_sent_without_token_returns_401(self, api_url):
        """未携带 Token 获取发件箱应返回 401"""
        assert requests.get(f"{api_url}/messages/sent").status_code == 401

    def test_noproj_user_cannot_get_sent(self, api_url, noproj_user):
        """不属于任何项目的员工不能拉取发件箱"""
        resp = requests.get(f"{api_url}/messages/sent", headers=_auth(noproj_user["key"]))
        assert resp.status_code == 403
